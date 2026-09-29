"""No AWS calls: exercise safety boundaries and the destructive restore ordering."""
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from botocore.response import StreamingBody

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import validation_baseline as baseline
from validation_maintenance import set_schedule


def bundle(tmp_path):
    directory = tmp_path / "baseline"
    directory.mkdir()
    (directory / "database.dump").write_bytes(b"dump")
    (directory / "object-00000000.bin").write_bytes(b"old content")
    manifest = {"format": 1, "complete": True, "identity": {"account": baseline.ACCOUNT},
                "created_at": "baseline", "database_summary": {"counts": {"public.faqs": 1}},
                "database": {"file": "database.dump", "sha256": baseline.digest(directory / "database.dump")},
                "objects": [{"key": "documents/admin/kb-source/word/1/a.docx", "file": "object-00000000.bin",
                             "attributes": {}, "sha256": baseline.digest(directory / "object-00000000.bin")}]}
    baseline.write_json(directory / "manifest.json", manifest)
    return directory, manifest


def environment(manifest):
    env = object.__new__(baseline.Environment)
    env.identity = manifest["identity"]
    env.pg = {"dbname": "scholarship"}
    env.pg_env = {}
    env.stopped = Mock()
    env.save = Mock()
    env.database_summary = Mock(return_value=manifest["database_summary"])
    env.s3 = Mock()
    env.bucket = "validation-only"
    env.targets = [("kb", "ds")]
    env.args = SimpleNamespace(sync_timeout=1)
    env.bedrock = Mock()
    env.bedrock.start_ingestion_job.return_value = {"ingestionJob": {"ingestionJobId": "job"}}
    env.bedrock.get_ingestion_job.return_value = {"ingestionJob": {"ingestionJobId": "job", "status": "COMPLETE",
                                                                   "statistics": {"numberOfDocumentsFailed": 0}}}
    return env


def prepare_restore(monkeypatch):
    monkeypatch.setattr(baseline.shutil, "which", lambda _: "/bin/test")
    run = Mock(return_value=SimpleNamespace(stdout=";     dbname: scholarship\n"))
    monkeypatch.setattr(baseline.subprocess, "run", run)
    return run


def test_modified_dump_rejected_before_aws_writes(tmp_path):
    directory, manifest = bundle(tmp_path)
    (directory / "database.dump").write_bytes(b"corrupt")
    env = environment(manifest)
    with pytest.raises(RuntimeError, match="Checksum"):
        env.restore(directory, tmp_path / "emergency", f"{baseline.ACCOUNT}/{baseline.STACK}")
    env.save.assert_not_called()
    env.s3.upload_file.assert_not_called()


@pytest.mark.parametrize("change", ["account", "confirmation"])
def test_wrong_environment_or_confirmation_blocks_restore(tmp_path, change):
    directory, manifest = bundle(tmp_path)
    env = environment(manifest)
    confirmation = f"{baseline.ACCOUNT}/{baseline.STACK}"
    if change == "account":
        env.identity = {"account": "other"}
    else:
        confirmation = "yes"
    with pytest.raises(RuntimeError):
        env.restore(directory, tmp_path / "emergency", confirmation)
    env.save.assert_not_called()


def test_emergency_failure_blocks_database_restore(tmp_path, monkeypatch):
    directory, manifest = bundle(tmp_path)
    env = environment(manifest)
    run = prepare_restore(monkeypatch)
    env.save.side_effect = RuntimeError("disk full")
    with pytest.raises(RuntimeError, match="disk full"):
        env.restore(directory, tmp_path / "emergency", f"{baseline.ACCOUNT}/{baseline.STACK}")
    assert len(run.call_args_list) == 1  # archive inspection only
    env.s3.upload_file.assert_not_called()


@pytest.mark.parametrize("failed_docs", [0, 1])
def test_restore_removes_extras_and_syncs_without_recrawl(tmp_path, monkeypatch, failed_docs):
    directory, manifest = bundle(tmp_path)
    env = environment(manifest)
    run = prepare_restore(monkeypatch)
    emergency = tmp_path / "emergency"
    env.save.side_effect = lambda path: path.mkdir()
    wanted = manifest["objects"][0]["key"]
    snapshots = iter([{wanted: {}, "added-after-baseline": {}}, {wanted: {}}])
    monkeypatch.setattr(baseline, "inventory", lambda *_: next(snapshots))
    env.s3.delete_objects.return_value = {}
    body = StreamingBody(io.BytesIO(b"old content"), len(b"old content"))
    env.s3.get_object.return_value = {"Body": body}
    env.bedrock.get_ingestion_job.return_value["ingestionJob"]["statistics"]["numberOfDocumentsFailed"] = failed_docs
    if failed_docs:
        with pytest.raises(RuntimeError, match="failed documents"):
            env.restore(directory, emergency, f"{baseline.ACCOUNT}/{baseline.STACK}")
        assert not (emergency / "restore-result.json").exists()
    else:
        env.restore(directory, emergency, f"{baseline.ACCOUNT}/{baseline.STACK}")
        assert (emergency / "restore-result.json").exists()
    assert "--create" in run.call_args_list[1].args[0]  # whole database replacement
    env.s3.delete_objects.assert_called_once_with(Bucket="validation-only", Delete={"Objects": [{"Key": "added-after-baseline"}]})
    env.bedrock.start_ingestion_job.assert_called_once_with(knowledgeBaseId="kb", dataSourceId="ds")


def test_backup_path_escape_rejected(tmp_path):
    directory, manifest = bundle(tmp_path)
    manifest["database"]["file"] = "../database.dump"
    baseline.write_json(directory / "manifest.json", manifest)
    with pytest.raises(RuntimeError, match="Unsafe"):
        baseline.verify_bundle(directory)


def test_scheduler_update_preserves_optional_values():
    client = Mock()
    original = {"Name": "nightly", "State": "ENABLED", "ScheduleExpression": "cron(...)" ,
                "ScheduleExpressionTimezone": "Asia/Tokyo", "Target": {"Arn": "target"},
                "FlexibleTimeWindow": {"Mode": "OFF"}, "KmsKeyArn": "key", "Arn": "readonly"}
    client.get_schedule.return_value = original
    client.meta.service_model.operation_model.return_value.input_shape.members = set(original) - {"Arn"}
    set_schedule(client, "nightly", "DISABLED")
    assert client.update_schedule.call_args.kwargs == {**{k: v for k, v in original.items() if k != "Arn"}, "State": "DISABLED"}


def test_wrong_aws_account_rejected_before_resource_access(monkeypatch):
    session = Mock()
    session.client.return_value.get_caller_identity.return_value = {"Account": "180162572038"}
    monkeypatch.setattr(baseline.boto3, "Session", lambda **_: session)
    with pytest.raises(RuntimeError, match="Wrong AWS account"):
        baseline.Environment(SimpleNamespace(profile=None))
    session.client.assert_called_once_with("sts")


def test_live_services_block_snapshot_before_db_or_s3():
    env = object.__new__(baseline.Environment)
    env.services = Mock(return_value=[{"desiredCount": 1, "runningCount": 1, "pendingCount": 0}])
    with pytest.raises(RuntimeError, match="Stop frontend"):
        env.stopped()


def test_s3_change_during_save_leaves_no_complete_manifest(tmp_path, monkeypatch):
    env = environment({"identity": {}, "database_summary": {"counts": {}}})
    env.pg["dbname"] = "scholarship"
    prepare_restore(monkeypatch)
    def dump(command, **kwargs):
        Path(command[command.index("--file") + 1]).write_bytes(b"dump")
    monkeypatch.setattr(baseline.subprocess, "run", dump)
    inventories = iter([{}, {"concurrent-write": {}}])
    monkeypatch.setattr(baseline, "inventory", lambda *_: next(inventories))
    directory = tmp_path / "incomplete"
    with pytest.raises(RuntimeError, match="S3 changed"):
        env.save = baseline.Environment.save.__get__(env)
        env.save(directory)
    assert not (directory / "manifest.json").exists()
    assert (directory / "incomplete.json").exists()


def test_self_test_target_cannot_select_development_or_arbitrary_stack():
    assert baseline.selected_target(SimpleNamespace(target='self-test')) == ('180162572038', 'ScholarshipChatbot-backup-rehearsal')
    assert baseline.selected_target(SimpleNamespace()) == (baseline.ACCOUNT, baseline.STACK)
    with pytest.raises(RuntimeError, match='Unsupported'):
        baseline.selected_target(SimpleNamespace(target='development'))
    for stack in [
        {'StackName': 'ScholarshipChatbot-development', 'Tags': [{'Key': 'Purpose', 'Value': 'backup-restore-test'}]},
        {'StackName': baseline.SELF_TEST_STACK, 'Tags': []},
    ]:
        with pytest.raises(RuntimeError, match='isolated'):
            baseline.verify_test_stack(stack, baseline.SELF_TEST_ACCOUNT)
    baseline.verify_test_stack({'StackName': baseline.SELF_TEST_STACK, 'Tags': [{'Key': 'Purpose', 'Value': 'backup-restore-test'}]}, baseline.SELF_TEST_ACCOUNT)


def test_save_reads_real_sdk_stream_and_closes_it(tmp_path, monkeypatch):
    env = environment({"identity": {}, "database_summary": {"counts": {}}})
    prepare_restore(monkeypatch)
    def dump(command, **kwargs):
        Path(command[command.index("--file") + 1]).write_bytes(b"dump")
    monkeypatch.setattr(baseline.subprocess, "run", dump)
    monkeypatch.setattr(baseline, "inventory", lambda *_: {"file.txt": {"ETag": "etag"}})
    raw = io.BytesIO(b"real SDK body")
    env.s3.get_object.return_value = {"Body": StreamingBody(raw, len(b"real SDK body"))}
    env.s3.get_object_tagging.return_value = {"TagSet": []}
    directory = tmp_path / "saved"
    baseline.Environment.save(env, directory)
    assert raw.closed
    manifest = baseline.verify_bundle(directory)
    assert (directory / manifest["objects"][0]["file"]).read_bytes() == b"real SDK body"


def test_pause_waits_for_actual_stop_after_desired_stop(monkeypatch):
    import validation_maintenance as maintenance
    ecs = Mock()
    monkeypatch.setattr(maintenance, "pages", lambda *a, **k: [])
    sleep = Mock()
    monkeypatch.setattr(maintenance.time, "sleep", sleep)
    ecs.describe_tasks.side_effect = [
        {"tasks": [{"taskArn": "task1", "lastStatus": status}]}
        for status in ["DEACTIVATING", "STOPPING", "STOPPED"]
    ]
    maintenance.wait_until_tasks_stopped(ecs, "cluster", ["task1"])
    assert sleep.call_count == 2
    assert ecs.describe_tasks.call_count == 3


def test_pause_refuses_unverifiable_task_state(monkeypatch):
    import validation_maintenance as maintenance
    ecs = Mock()
    monkeypatch.setattr(maintenance, "pages", lambda *a, **k: [])
    ecs.describe_tasks.return_value = {"tasks": [], "failures": [{"arn": "task1"}]}
    with pytest.raises(RuntimeError, match="Cannot verify task termination"):
        maintenance.wait_until_tasks_stopped(ecs, "cluster", ["task1"])
