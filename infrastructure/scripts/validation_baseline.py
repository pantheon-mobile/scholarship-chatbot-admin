#!/usr/bin/env python3
"""Offline-coordinated, whole-data baseline for the customer validation stack.

No credentials or AWS mutations occur at import time. See the operator runbook.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import boto3
import psycopg
from psycopg import sql

ACCOUNT = "796575284584"
STACK = "ScholarshipChatbot-stg01-demo"
ACTIVE_JOBS = {"STARTING", "IN_PROGRESS", "STOPPING"}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    temporary.replace(path)


def now():
    return datetime.now(timezone.utc).isoformat()


def pages(client, operation, field, **kwargs):
    for page in client.get_paginator(operation).paginate(**kwargs):
        yield from page.get(field, [])


def inventory(s3, bucket):
    return {o["Key"]: {k: str(o[k]) for k in ("ETag", "Size", "LastModified")}
            for o in pages(s3, "list_objects_v2", "Contents", Bucket=bucket)}


def verify_bundle(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    require(manifest.get("format") == 1 and manifest.get("complete") is True,
            "Incomplete or unsupported backup")
    entries = [manifest["database"], *manifest["objects"]]
    names = set()
    keys = set()
    for entry in entries:
        name = entry["file"]
        require(name not in names, "Duplicate backup file")
        names.add(name)
        path = directory / name
        require(not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()),
                "Unsafe backup path")
        require(path.is_file() and digest(path) == entry["sha256"], f"Checksum mismatch: {name}")
    for obj in manifest["objects"]:
        require(obj["key"] not in keys, "Duplicate S3 key")
        keys.add(obj["key"])
    return manifest


class Environment:
    def __init__(self, args):
        self.args = args
        self.session = boto3.Session(profile_name=args.profile, region_name="ap-northeast-1")
        self.sts = self.session.client("sts")
        require(self.sts.get_caller_identity()["Account"] == ACCOUNT,
                "Wrong AWS account: this tool is restricted to customer validation")
        self.cf = self.session.client("cloudformation")
        stack = self.cf.describe_stacks(StackName=STACK)["Stacks"][0]
        require(stack["StackStatus"] in {"CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"},
                "Stack is not stable")
        self.outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}
        self.bucket = self.outputs["DocumentsBucketName"]
        resources = list(pages(self.cf, "list_stack_resources", "StackResourceSummaries", StackName=STACK))
        require(any(r["ResourceType"] == "AWS::S3::Bucket" and
                    r["PhysicalResourceId"] == self.bucket for r in resources),
                "Only a dedicated bucket owned by this validation stack is supported")
        self.ecs = self.session.client("ecs")
        self.s3 = self.session.client("s3")
        self.scheduler = self.session.client("scheduler")
        self.bedrock = self.session.client("bedrock-agent")
        self.cluster = self.outputs["ClusterName"]
        self.service_names = [self.outputs[k] for k in ("FrontendServiceName", "BackendServiceName")]
        services = self.services()
        backend = next(s for s in services if s["serviceName"] == self.outputs["BackendServiceName"])
        task = self.ecs.describe_task_definition(taskDefinition=backend["taskDefinition"])["taskDefinition"]
        container = next(c for c in task["containerDefinitions"] if c["name"] == "backend")
        env = {e["name"]: e["value"] for e in container["environment"]}
        require(env["INGESTION_S3_BUCKET"] == self.bucket and env["STORAGE_BACKEND"] == "s3",
                "Unexpected application storage configuration")
        self.targets = sorted(set((env[f"INGESTION_{kind}_KNOWLEDGE_BASE_ID"],
                                   env[f"INGESTION_{kind}_DATA_SOURCE_ID"])
                                  for kind in ["PDF", "WEB", "EXCEL", "WORD", "PPT", "TEXT"]))
        configs = []
        for kb, ds in self.targets:
            data = self.bedrock.get_data_source(knowledgeBaseId=kb, dataSourceId=ds)["dataSource"]
            require(data["status"] == "AVAILABLE", "Bedrock data source is not available")
            conf = data["dataSourceConfiguration"]
            require(conf["type"] == "S3" and conf["s3Configuration"]["bucketArn"] == f"arn:aws:s3:::{self.bucket}",
                    "Knowledge Base uses a different bucket")
            configs.append({"kb": kb, "ds": ds, "source": conf,
                            "ingestion": data.get("vectorIngestionConfiguration", {})})
        self.identity = {"account": ACCOUNT, "region": "ap-northeast-1", "stack": stack["StackId"],
                         "bucket": self.bucket, "cluster": self.cluster, "search": configs,
                         "task_definitions": sorted(s["taskDefinition"] for s in services),
                         "db_host": env["DB_HOST"], "db_name": env["DB_NAME"]}
        require(env["DB_NAME"] == "scholarship", "Unexpected database name")
        secret = self.session.client("secretsmanager").get_secret_value(
            SecretId=self.outputs["DatabaseSecretName"])
        credentials = json.loads(secret["SecretString"])
        self.pg = {"host": args.db_host or env["DB_HOST"], "port": args.db_port or env["DB_PORT"],
                   "dbname": env["DB_NAME"], "user": credentials["username"],
                   "password": credentials["password"], "sslmode": "require", "connect_timeout": 15}
        self.pg_env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
        self.pg_env.update({"PGHOST": self.pg["host"], "PGPORT": str(self.pg["port"]),
                            "PGUSER": self.pg["user"], "PGPASSWORD": self.pg["password"],
                            "PGSSLMODE": "require", "PGCONNECT_TIMEOUT": "15"})

    def services(self):
        result = self.ecs.describe_services(cluster=self.cluster, services=self.service_names)
        require(not result.get("failures") and len(result["services"]) == 2, "Cannot identify both ECS services")
        return result["services"]

    def stopped(self):
        require(all(s["desiredCount"] == 0 and s["runningCount"] == 0 and s["pendingCount"] == 0
                    for s in self.services()), "Stop frontend and backend services first")
        tasks = list(pages(self.ecs, "list_tasks", "taskArns", cluster=self.cluster, desiredStatus="RUNNING"))
        require(not tasks, "ECS tasks are still running/pending (including ingestion workers)")
        schedule = self.scheduler.get_schedule(Name=self.outputs["NightlyIngestionScheduleName"])
        require(schedule["State"] == "DISABLED", "Disable nightly ingestion schedule first")
        for kb, ds in self.targets:
            jobs = pages(self.bedrock, "list_ingestion_jobs", "ingestionJobSummaries",
                         knowledgeBaseId=kb, dataSourceId=ds)
            require(not any(j["status"] in ACTIVE_JOBS for j in jobs), "A Bedrock ingestion job is active")
        with psycopg.connect(**self.pg) as conn:
            sessions = conn.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()").fetchone()[0]
            require(sessions == 0, "Other database sessions exist; disconnect writers and operators")

    def database_summary(self):
        with psycopg.connect(**self.pg) as conn:
            tables = conn.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2").fetchall()
            counts = {}
            for schema, table in tables:
                counts[f"{schema}.{table}"] = conn.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(
                    sql.Identifier(schema), sql.Identifier(table))).fetchone()[0]
            return {"counts": counts, "version": conn.execute("SHOW server_version_num").fetchone()[0]}

    def save(self, directory):
        require(shutil.which("pg_dump") and shutil.which("pg_restore"), "Install PostgreSQL client tools first")
        self.stopped()
        directory.mkdir(parents=True, exist_ok=False, mode=0o700)
        manifest = {"format": 1, "complete": False, "created_at": now(), "identity": self.identity}
        write_json(directory / "incomplete.json", manifest)
        initial = inventory(self.s3, self.bucket)
        manifest["database_summary"] = self.database_summary()
        dump = directory / "database.dump"
        subprocess.run(["pg_dump", "--format=custom", "--create", "--file", str(dump),
                        "--dbname", self.pg["dbname"]], env=self.pg_env, check=True)
        manifest["database"] = {"file": dump.name, "sha256": digest(dump)}
        objects = []
        for index, (key, before) in enumerate(sorted(initial.items())):
            response = self.s3.get_object(Bucket=self.bucket, Key=key, IfMatch=before["ETag"])
            path = directory / f"object-{index:08d}.bin"
            with response["Body"] as body, path.open("wb") as output:
                for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                    output.write(chunk)
            attrs = {k: response[k] for k in ["ContentType", "ContentLanguage", "ContentEncoding",
                                            "ContentDisposition", "CacheControl", "Metadata"] if k in response}
            if response.get("Expires"):
                attrs["Expires"] = response["Expires"].isoformat()
            tag_args = {"Bucket": self.bucket, "Key": key}
            if response.get("VersionId"):
                tag_args["VersionId"] = response["VersionId"]
            tags = self.s3.get_object_tagging(**tag_args)["TagSet"]
            if tags:
                attrs["Tagging"] = urlencode([(t["Key"], t["Value"]) for t in tags])
            objects.append({"key": key, "file": path.name, "sha256": digest(path), "attributes": attrs,
                            "version_id": response.get("VersionId"), "size": path.stat().st_size})
        self.stopped()
        require(initial == inventory(self.s3, self.bucket), "S3 changed during backup; discard incomplete backup")
        require(manifest["database_summary"] == self.database_summary(), "Database changed during backup")
        manifest.update(objects=objects, complete=True, completed_at=now())
        write_json(directory / "manifest.json", manifest)
        (directory / "incomplete.json").unlink()
        verify_bundle(directory)
        print(f"Saved and checksum-verified: {directory} ({len(objects)} S3 objects)")

    def restore(self, directory, emergency, confirmation):
        manifest = verify_bundle(directory)
        require(manifest["identity"] == self.identity, "Environment/configuration differs from baseline; do not restore")
        require(confirmation == f"{ACCOUNT}/{STACK}", "Explicit --confirm account/stack is required")
        require(shutil.which("pg_restore"), "Install PostgreSQL client tools first")
        archive = subprocess.run(["pg_restore", "--list", str(directory / manifest["database"]["file"])],
                                 capture_output=True, text=True, check=True).stdout
        require(any(line.strip() == f";     dbname: {self.pg['dbname']}" for line in archive.splitlines()),
                "Archive database name does not match target")
        self.stopped()
        # Mandatory rollback point, made before any destructive operation.
        self.save(emergency)
        self.stopped()
        print("Restoring DB; application will remain stopped on success or failure.", flush=True)
        subprocess.run(["pg_restore", "--exit-on-error", "--clean", "--if-exists", "--create",
                        "--dbname", "postgres", str(directory / manifest["database"]["file"])],
                       env=self.pg_env, check=True)
        require(self.database_summary() == manifest["database_summary"], "Restored table counts/version differ")
        wanted = {o["key"] for o in manifest["objects"]}
        for obj in manifest["objects"]:
            attrs = dict(obj["attributes"])
            if "Expires" in attrs:
                attrs["Expires"] = datetime.fromisoformat(attrs["Expires"])
            self.s3.upload_file(str(directory / obj["file"]), self.bucket, obj["key"], ExtraArgs=attrs)
        extra = sorted(set(inventory(self.s3, self.bucket)) - wanted)
        for start in range(0, len(extra), 1000):
            result = self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": [
                {"Key": key} for key in extra[start:start + 1000]]})
            require(not result.get("Errors"), "Some extra S3 objects could not be deleted")
        require(set(inventory(self.s3, self.bucket)) == wanted, "Restored S3 key list differs")
        for obj in manifest["objects"]:
            with self.s3.get_object(Bucket=self.bucket, Key=obj["key"])["Body"] as body:
                sha = hashlib.sha256()
                for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                    sha.update(chunk)
                require(sha.hexdigest() == obj["sha256"], "Restored S3 content checksum differs")
        # Direct KB sync: do NOT run application ingestion (which would recrawl/reconvert).
        results = []
        for kb, ds in self.targets:
            job = self.bedrock.start_ingestion_job(knowledgeBaseId=kb, dataSourceId=ds)["ingestionJob"]
            deadline = time.monotonic() + self.args.sync_timeout
            while True:
                job = self.bedrock.get_ingestion_job(knowledgeBaseId=kb, dataSourceId=ds,
                                                     ingestionJobId=job["ingestionJobId"])["ingestionJob"]
                if job["status"] not in ACTIVE_JOBS:
                    break
                require(time.monotonic() < deadline, "KB sync timed out; keep services stopped and inspect job")
                time.sleep(10)
            require(job["status"] == "COMPLETE" and job.get("statistics", {}).get("numberOfDocumentsFailed", 0) == 0,
                    "KB sync failed or contains failed documents; keep services stopped")
            results.append({"kb": kb, "ds": ds, "job": job["ingestionJobId"], "statistics": job.get("statistics", {})})
        self.stopped()
        write_json(emergency / "restore-result.json", {"completed_at": now(), "baseline": str(directory.resolve()),
                                                       "search_jobs": results})
        print("Restore verified. Keep schedule disabled; follow the runbook to restart and check answers.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inspect", "save", "verify", "restore"])
    parser.add_argument("--profile")
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--emergency-directory", type=Path)
    parser.add_argument("--confirm")
    parser.add_argument("--db-host", help="Optional SSM tunnel endpoint, e.g. 127.0.0.1")
    parser.add_argument("--db-port", type=int)
    parser.add_argument("--sync-timeout", type=int, default=7200)
    args = parser.parse_args()
    os.umask(0o077)
    if args.action != "inspect":
        require(args.directory is not None, "--directory is required")
    if args.action == "verify":
        manifest = verify_bundle(args.directory)
        print(f"Backup checksums OK: {manifest['created_at']}, {len(manifest['objects'])} objects")
        return
    env = Environment(args)
    if args.action == "inspect":
        print(json.dumps({"identity": env.identity, "outputs": env.outputs,
                          "services": [{k: s[k] for k in ["serviceName", "desiredCount", "runningCount", "taskDefinition"]}
                                       for s in env.services()]}, ensure_ascii=False, indent=2))
    elif args.action == "save":
        env.save(args.directory)
    else:
        require(args.emergency_directory is not None, "--emergency-directory is required")
        env.restore(args.directory, args.emergency_directory, args.confirm)


if __name__ == "__main__":
    main()
