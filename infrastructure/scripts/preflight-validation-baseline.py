#!/usr/bin/env python3
"""Read-only checks before arranging a customer validation backup outage.

Does not stop services, start ingestion, write S3 objects or mutate the database.
This cannot prove permissions for write/restore operations.
"""
import argparse
import json
import shutil
import subprocess
import re
from pathlib import Path

import psycopg
from botocore.exceptions import ClientError

from validation_baseline import ACCOUNT, Environment, pages

BACKUP_BUCKET = "gakupita.backup"
BACKUP_PREFIX = "ai-chatbot/stg01-demo/"
EXPECTED_ROLE = "dev-gakupita-app-build-server-role"


def check_database(pg):
    with psycopg.connect(**pg, options="-c default_transaction_read_only=on -c statement_timeout=15000") as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_setting('server_version_num')::int, pg_database_size(current_database()), current_user")
            version, size, user = cursor.fetchone()
    return {"server_major": version // 10000, "database_bytes": size, "database_user": user}


def tool_versions(server_major):
    results = {}
    for tool in ("pg_dump", "pg_restore"):
        if not shutil.which(tool):
            raise RuntimeError(f"Install {tool} matching PostgreSQL {server_major}")
        output = subprocess.run([tool, "--version"], check=True, capture_output=True, text=True, timeout=10).stdout
        match = re.search(r"(\d+)\.", output)
        if not match or int(match[1]) != server_major:
            raise RuntimeError(f"{tool} must match PostgreSQL {server_major}")
        results[tool] = output.strip()
    return results


def inspect(env, directory):
    if not directory.is_dir():
        raise RuntimeError("--work-directory must be an existing directory")
    caller = env.sts.get_caller_identity()
    report = {"account": caller['Account'], "caller_arn": caller['Arn'],
              "expected_instance_role": EXPECTED_ROLE,
              "instance_role_matches": f":assumed-role/{EXPECTED_ROLE}/" in caller['Arn'],
              "stack": env.identity['stack'], "source_bucket": env.bucket,
              "backup_uri": f"s3://{BACKUP_BUCKET}/{BACKUP_PREFIX}",
              "services": [{key: row[key] for key in ('serviceName', 'desiredCount', 'runningCount')}
                           for row in env.services()]}
    if env.bucket == BACKUP_BUCKET:
        raise RuntimeError("Backup destination must differ from the application bucket")
    report['database'] = check_database(env.pg)
    report['tools'] = tool_versions(report['database']['server_major'])
    count = total = 0
    for obj in pages(env.s3, 'list_objects_v2', 'Contents', Bucket=env.bucket):
        count += 1
        total += obj['Size']
    report['source_objects'] = count
    report['source_bytes'] = total
    report['work_directory_free_bytes'] = shutil.disk_usage(directory).free
    report['uncompressed_data_bytes_estimate'] = total + report['database']['database_bytes']
    # A bounded read confirms the agreed prefix is readable without any test writes.
    env.s3.list_objects_v2(Bucket=BACKUP_BUCKET, Prefix=BACKUP_PREFIX, MaxKeys=1, ExpectedBucketOwner=ACCOUNT)
    for label, operation in [('lifecycle', env.s3.get_bucket_lifecycle_configuration),
                             ('encryption', env.s3.get_bucket_encryption),
                             ('versioning', env.s3.get_bucket_versioning)]:
        try:
            settings = operation(Bucket=BACKUP_BUCKET, ExpectedBucketOwner=ACCOUNT)
            settings.pop('ResponseMetadata', None)
            report[label] = settings
        except ClientError as exc:
            # No secret values or raw service exception text are printed.
            report[label] = {"unverified_error_code": exc.response['Error']['Code']}
    report['limitations'] = [
        'Read-only checks do not prove S3/KMS write, ECS/Scheduler update, iam:PassRole or restore permissions.',
        'Confirm the effective lifecycle for this prefix, including noncurrent versions; customer-approved retention is 183 days.',
        'Disk estimate excludes temporary files and before-restore backup; allow additional space.',
        'The work directory encryption, access control and existing deployments must be checked by the operator.',
        'No services were stopped and no backup was created.',
    ]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', help='Omit on EC2 to use its instance role (remove unrelated credential overrides).')
    parser.add_argument('--db-host')
    parser.add_argument('--db-port', type=int)
    parser.add_argument('--work-directory', required=True, type=Path)
    args = parser.parse_args()
    # Environment checks the customer account, stable stack and dedicated source bucket.
    env = Environment(args)
    print(json.dumps(inspect(env, args.work_directory), ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
