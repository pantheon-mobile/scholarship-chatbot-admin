import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('preflight', SCRIPTS / 'preflight-validation-baseline.py')
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def environment(monkeypatch):
    env = SimpleNamespace(sts=Mock(), s3=Mock(), pg={}, identity={'stack': 'validation-stack'}, bucket='application-documents', services=lambda: [])
    env.sts.get_caller_identity.return_value = {'Account': preflight.ACCOUNT, 'Arn': f'arn:aws:sts::{preflight.ACCOUNT}:assumed-role/{preflight.EXPECTED_ROLE}/instance'}
    env.s3.get_paginator.return_value.paginate.return_value = [{'Contents': [{'Key': 'original.pdf', 'Size': 20}]}]
    env.s3.get_bucket_lifecycle_configuration.return_value = {'Rules': [{'Status': 'Enabled', 'Expiration': {'Days': 183}}]}
    env.s3.get_bucket_encryption.return_value = {}
    env.s3.get_bucket_versioning.return_value = {}
    monkeypatch.setattr(preflight, 'check_database', lambda pg: {'server_major': 16, 'database_bytes': 100, 'database_user': 'admin'})
    monkeypatch.setattr(preflight, 'tool_versions', lambda major: {})
    return env


def test_preflight_is_read_only_and_does_not_claim_backup_success(tmp_path, monkeypatch):
    env = environment(monkeypatch)
    result = preflight.inspect(env, tmp_path)
    assert result['instance_role_matches']
    assert result['uncompressed_data_bytes_estimate'] == 120
    assert result['backup_uri'] == 's3://gakupita.backup/ai-chatbot/stg01-demo/'
    assert 'no backup was created' in result['limitations'][-1]
    calls = {call[0] for call in env.s3.mock_calls}
    assert calls <= {'get_paginator', 'get_paginator().paginate', 'list_objects_v2', 'get_bucket_lifecycle_configuration', 'get_bucket_encryption', 'get_bucket_versioning'}


def test_settings_permission_failure_is_not_reported_as_verified(tmp_path, monkeypatch):
    env = environment(monkeypatch)
    env.s3.get_bucket_lifecycle_configuration.side_effect = ClientError({'Error': {'Code': 'AccessDenied', 'Message': 'secret-like debug text'}}, 'GetBucketLifecycleConfiguration')
    result = preflight.inspect(env, tmp_path)
    assert result['lifecycle'] == {'unverified_error_code': 'AccessDenied'}
    assert 'secret-like' not in str(result)


def test_shared_backup_bucket_never_used_as_source(tmp_path, monkeypatch):
    env = environment(monkeypatch)
    env.bucket = preflight.BACKUP_BUCKET
    with pytest.raises(RuntimeError, match='must differ'):
        preflight.inspect(env, tmp_path)
    assert not env.s3.mock_calls


def test_pg_tool_major_must_match_server(monkeypatch):
    monkeypatch.setattr(preflight.shutil, 'which', lambda _: '/bin/tool')
    monkeypatch.setattr(preflight.subprocess, 'run', lambda *a, **kw: SimpleNamespace(stdout='pg_dump (PostgreSQL) 15.4'))
    with pytest.raises(RuntimeError, match='PostgreSQL 16'):
        preflight.tool_versions(16)
