"""Opt-in round trip using a disposable DB in the existing local postgres container.

BASELINE_TEST_POSTGRES_CONTAINER=scholarship-chatbot-admin-db-1 pytest ...
Only uniquely named codex_baseline_test_* databases are created/dropped.
AWS is entirely simulated; pg_dump/pg_restore and SQL are real.
"""
import io
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import psycopg
from psycopg import sql
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import validation_baseline as baseline

CONTAINER = os.getenv("BASELINE_TEST_POSTGRES_CONTAINER")
pytestmark = pytest.mark.skipif(not CONTAINER, reason="Opt-in local Postgres container required")


class Body(io.BytesIO):
    def iter_chunks(self, chunk_size):
        while chunk := self.read(chunk_size):
            yield chunk


class S3:
    def __init__(self):
        self.objects = {"documents/admin/kb-source/web/1/page.md": b"baseline web text",
                        "documents/admin/kb-source/web/1/page.md.metadata.json": b'{"title":"baseline"}'}

    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        return SimpleNamespace(paginate=lambda **_: [{"Contents": [
            {"Key": k, "ETag": str(v), "Size": len(v), "LastModified": "constant"}
            for k, v in self.objects.items()]}])

    def get_object(self, **kwargs):
        value = self.objects[kwargs["Key"]]
        return {"Body": Body(value), "ContentType": "text/plain", "Metadata": {"test": "baseline"}}

    def get_object_tagging(self, **kwargs):
        return {"TagSet": []}

    def upload_file(self, path, bucket, key, ExtraArgs):
        self.objects[key] = Path(path).read_bytes()

    def delete_objects(self, Bucket, Delete):
        for obj in Delete["Objects"]:
            del self.objects[obj["Key"]]
        return {}


def test_full_database_and_s3_roundtrip(tmp_path, monkeypatch):
    database = "codex_baseline_test_" + uuid.uuid4().hex[:12]
    connection = dict(host="localhost", port=5432, user="postgres", password="postgres")
    real_run = subprocess.run
    def postgres_tool(command, **kwargs):
        tool, *args = command
        if tool == "pg_dump":
            index = args.index("--file")
            output = Path(args[index + 1])
            del args[index:index + 2]
            result = real_run(["docker", "exec", CONTAINER, tool, "-U", "postgres", *args],
                              capture_output=True, check=True)
            output.write_bytes(result.stdout)
            return result
        archive = Path(args.pop()).read_bytes()
        result = real_run(["docker", "exec", "-i", CONTAINER, tool, "-U", "postgres", *args],
                          input=archive, capture_output=True, check=True)
        return SimpleNamespace(stdout=result.stdout.decode())
    monkeypatch.setattr(baseline.subprocess, "run", postgres_tool)
    monkeypatch.setattr(baseline.shutil, "which", lambda _: "docker")
    with psycopg.connect(**connection, dbname="postgres", autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            pg = dict(connection, dbname=database)
            with psycopg.connect(**pg) as conn:
                conn.execute("CREATE TABLE faqs (id bigserial PRIMARY KEY, answer text NOT NULL)")
                conn.execute("INSERT INTO faqs(answer) VALUES ('baseline answer')")
            env = object.__new__(baseline.Environment)
            env.pg, env.pg_env = pg, {}
            env.identity = {"test": database}
            env.bucket = "fake-only"
            env.s3 = S3()
            env.stopped = Mock()  # No AWS; SQL is in a newly created isolated DB.
            env.targets = [("fake-kb", "fake-ds")]
            env.args = SimpleNamespace(sync_timeout=10)
            env.bedrock = Mock()
            job = {"ingestionJobId": "fake-job", "status": "COMPLETE", "statistics": {"numberOfDocumentsFailed": 0}}
            env.bedrock.start_ingestion_job.return_value = {"ingestionJob": job}
            env.bedrock.get_ingestion_job.return_value = {"ingestionJob": job}
            directory = tmp_path / "baseline"
            env.save(directory)
            with psycopg.connect(**pg) as conn:
                conn.execute("UPDATE faqs SET answer='changed'")
                conn.execute("INSERT INTO faqs(answer) VALUES ('added later')")
                conn.execute("CREATE TABLE added_after_backup (id integer)")
            env.s3.objects["documents/admin/kb-source/web/1/page.md"] = b"changed web text"
            env.s3.objects["documents/admin/added-after-backup"] = b"extra"
            emergency = tmp_path / "emergency"
            env.restore(directory, emergency, f"{baseline.ACCOUNT}/{baseline.STACK}")
            with psycopg.connect(**pg) as conn:
                assert conn.execute("SELECT id,answer FROM faqs").fetchall() == [(1, "baseline answer")]
                assert conn.execute("SELECT to_regclass('public.added_after_backup')").fetchone()[0] is None
                assert conn.execute("INSERT INTO faqs(answer) VALUES ('next') RETURNING id").fetchone()[0] == 2
            assert env.s3.objects["documents/admin/kb-source/web/1/page.md"] == b"baseline web text"
            assert "documents/admin/added-after-backup" not in env.s3.objects
            emergency_manifest = baseline.verify_bundle(emergency)
            assert emergency_manifest["database_summary"]["counts"]["public.faqs"] == 2
            assert (emergency / "restore-result.json").exists()
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
