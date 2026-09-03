from __future__ import annotations

import asyncio
import logging
import os
import sys

import boto3


logger = logging.getLogger(__name__)


async def launch_ingestion_worker() -> None:
    """Run the same queue worker used by the nightly scheduled task."""
    cluster = os.getenv("INGESTION_ECS_CLUSTER_ARN", "").strip()
    task_definition = os.getenv("INGESTION_ECS_TASK_DEFINITION_ARN", "").strip()
    if cluster and task_definition:
        await asyncio.to_thread(_launch_ecs_worker, cluster, task_definition)
        return

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.worker",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    message = output.decode("utf-8", errors="replace").strip()
    if process.returncode == 0:
        logger.info("manually launched ingestion worker completed: %s", message)
        return
    logger.error(
        "manually launched ingestion worker failed (exit=%s): %s",
        process.returncode,
        message,
    )
    raise RuntimeError(f"取り込みワーカーの起動に失敗しました: {message or process.returncode}")


def _launch_ecs_worker(cluster: str, task_definition: str) -> None:
    subnets = [value.strip() for value in os.getenv("INGESTION_ECS_SUBNET_IDS", "").split(",") if value.strip()]
    security_groups = [value.strip() for value in os.getenv("INGESTION_ECS_SECURITY_GROUP_IDS", "").split(",") if value.strip()]
    if not subnets or not security_groups:
        raise RuntimeError("ECS取り込みワーカー用のSubnetまたはSecurity Groupが未設定です。")
    response = boto3.client(
        "ecs", region_name=os.getenv("AWS_REGION", "ap-northeast-1")
    ).run_task(
        cluster=cluster,
        taskDefinition=task_definition,
        launchType="FARGATE",
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnets,
                "securityGroups": security_groups,
                "assignPublicIp": "DISABLED",
            }
        },
    )
    failures = response.get("failures", [])
    if failures:
        reasons = "; ".join(item.get("reason", "unknown") for item in failures)
        raise RuntimeError(f"ECS取り込みワーカーの起動に失敗しました: {reasons}")
    task_arns = [item.get("taskArn") for item in response.get("tasks", []) if item.get("taskArn")]
    if not task_arns:
        raise RuntimeError("ECS取り込みワーカーのTask ARNを取得できませんでした。")
    logger.info("manually launched ECS ingestion worker: %s", task_arns[0])
