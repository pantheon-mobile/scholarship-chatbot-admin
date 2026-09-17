#!/usr/bin/env python3
"""Pause/restart validation services without changing their task definitions."""
import argparse
import json
import os
from pathlib import Path
import time

import boto3

from validation_baseline import ACCOUNT, STACK, pages, require, write_json


def set_schedule(client, name, state):
    current = client.get_schedule(Name=name)
    allowed = client.meta.service_model.operation_model("UpdateSchedule").input_shape.members
    # GetSchedule/UpdateSchedule must preserve optional fields (including dates).
    payload = {k: v for k, v in current.items() if k in allowed}
    payload["State"] = state
    client.update_schedule(**payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["pause", "start-app", "resume-schedule"])
    parser.add_argument("--profile")
    parser.add_argument("--state", required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    session = boto3.Session(profile_name=args.profile, region_name="ap-northeast-1")
    require(session.client("sts").get_caller_identity()["Account"] == ACCOUNT, "Wrong AWS account")
    stack = session.client("cloudformation").describe_stacks(StackName=STACK)["Stacks"][0]
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}
    cluster, schedule = outputs["ClusterName"], outputs["NightlyIngestionScheduleName"]
    ecs, scheduler = session.client("ecs"), session.client("scheduler")
    if args.action == "pause":
        require(not args.state.exists(), "State file already exists; retain it and inspect the previous pause")
        names = [outputs[k] for k in ["FrontendServiceName", "BackendServiceName"]]
        response = ecs.describe_services(cluster=cluster, services=names)
        require(not response.get("failures") and len(response["services"]) == 2, "Services not found")
        state = {"stack": stack["StackId"], "cluster": cluster, "schedule": schedule,
                 "schedule_state": scheduler.get_schedule(Name=schedule)["State"],
                 "services": [{"name": s["serviceName"], "desired": s["desiredCount"],
                               "task_definition": s["taskDefinition"]} for s in response["services"]]}
        args.state.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.state, state)  # Save BEFORE any mutation; never auto-resume on failure.
        set_schedule(scheduler, schedule, "DISABLED")
        for service in state["services"]:
            ecs.update_service(cluster=cluster, service=service["name"], desiredCount=0)
        deadline = time.monotonic() + 7200
        while list(pages(ecs, "list_tasks", "taskArns", cluster=cluster, desiredStatus="RUNNING")):
            require(time.monotonic() < deadline, "Tasks did not finish; leave services stopped and investigate")
            print("Waiting for services/workers to stop (workers are NOT forcibly terminated)...", flush=True)
            time.sleep(20)
        print("Paused. Check Scheduler retry window, DB jobs and Bedrock jobs per runbook before saving.")
        return
    state = json.loads(args.state.read_text())
    require((state["stack"], state["cluster"], state["schedule"]) == (stack["StackId"], cluster, schedule),
            "State file belongs to a different environment")
    if args.action == "start-app":
        for service in state["services"]:
            current = ecs.describe_services(cluster=cluster, services=[service["name"]])["services"][0]
            require(current["taskDefinition"] == service["task_definition"], "Task definition changed while paused")
        for service in state["services"]:
            ecs.update_service(cluster=cluster, service=service["name"], desiredCount=service["desired"])
        ecs.get_waiter("services_stable").wait(cluster=cluster, services=[s["name"] for s in state["services"]])
        print("Application restarted. Scheduler remains disabled; inspect before resuming it.")
    else:
        set_schedule(scheduler, schedule, state["schedule_state"])
        print(f"Scheduler restored to {state['schedule_state']}. Automatic recrawling may change restored content.")


if __name__ == "__main__":
    main()
