from unittest.mock import MagicMock

import pytest

from app.services import ingestion_launcher


@pytest.mark.anyio
async def test_launches_dedicated_ecs_worker_when_configured(monkeypatch):
    monkeypatch.setenv("INGESTION_ECS_CLUSTER_ARN", "cluster-arn")
    monkeypatch.setenv("INGESTION_ECS_TASK_DEFINITION_ARN", "task-definition-arn")
    launch = MagicMock()
    monkeypatch.setattr(ingestion_launcher, "_launch_ecs_worker", launch)

    await ingestion_launcher.launch_ingestion_worker()

    launch.assert_called_once_with("cluster-arn", "task-definition-arn")


def test_ecs_worker_uses_private_network(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "ap-northeast-1")
    monkeypatch.setenv("INGESTION_ECS_SUBNET_IDS", "subnet-a,subnet-b")
    monkeypatch.setenv("INGESTION_ECS_SECURITY_GROUP_IDS", "sg-worker")
    ecs = MagicMock()
    ecs.run_task.return_value = {"tasks": [{"taskArn": "worker-task-arn"}], "failures": []}
    monkeypatch.setattr(ingestion_launcher.boto3, "client", lambda *args, **kwargs: ecs)

    ingestion_launcher._launch_ecs_worker("cluster-arn", "task-definition-arn")

    ecs.run_task.assert_called_once_with(
        cluster="cluster-arn",
        taskDefinition="task-definition-arn",
        launchType="FARGATE",
        count=1,
        networkConfiguration={"awsvpcConfiguration": {
            "subnets": ["subnet-a", "subnet-b"],
            "securityGroups": ["sg-worker"],
            "assignPublicIp": "DISABLED",
        }},
    )


def test_ecs_worker_reports_run_task_failure(monkeypatch):
    monkeypatch.setenv("INGESTION_ECS_SUBNET_IDS", "subnet-a")
    monkeypatch.setenv("INGESTION_ECS_SECURITY_GROUP_IDS", "sg-worker")
    ecs = MagicMock()
    ecs.run_task.return_value = {"tasks": [], "failures": [{"reason": "capacity unavailable"}]}
    monkeypatch.setattr(ingestion_launcher.boto3, "client", lambda *args, **kwargs: ecs)

    with pytest.raises(RuntimeError, match="capacity unavailable"):
        ingestion_launcher._launch_ecs_worker("cluster-arn", "task-definition-arn")
