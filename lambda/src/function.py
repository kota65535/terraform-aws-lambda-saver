import json
import logging
import os
from datetime import datetime

import boto3
from pytz import timezone

# ========== Environment Variables to be configured ==========
TIMEZONE = os.getenv("TIMEZONE", "UTC")

# ========== Logger ==========
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Boto3 client
lambda_client = boto3.client("lambda")


def lambda_handler(event: dict, context: dict):
    logger.info(f"Input: {json.dumps(event)}")

    if "action" in event:
        # Force start/stop lambdas

        action = event["action"]
        if action not in ["start", "stop"]:
            raise Exception(f"unsupported action: {action}")

        if "function" in event:
            function = event["function"]
            if action == "stop":
                stop_lambda_function_by_name(function)
            if action == "start":
                start_lambda_function_by_name(function)
        elif "tags" in event:
            tags = event["tags"]
            if action == "stop":
                stop_lambda_functions_by_tags(tags)
            if action == "start":
                start_lambda_functions_by_tags(tags)
        else:
            raise Exception("either function or tags must be specified")
    else:
        # Scheduled start/stop

        now = datetime.now(tz=timezone(TIMEZONE))
        current_hour = now.hour
        current_weekday = now.isoweekday()

        # For debug
        if "hour" in event:
            current_hour = event["hour"]
        if "weekday" in event:
            current_weekday = event["weekday"]

        logger.info(f"hour: {current_hour}, weekday: {current_weekday}")

        stop_lambda_functions_by_schedule(current_hour, current_weekday)
        start_lambda_functions_by_schedule(current_hour, current_weekday)


def stop_lambda_function_by_name(function_name: str):
    res = lambda_client.get_function(FunctionName=function_name)
    function = res["Configuration"]
    res = lambda_client.list_tags(Resource=function["FunctionArn"])
    function["Tags"] = res.get("Tags", {})

    stop_lambda_function(function)


def start_lambda_function_by_name(function_name: str):
    res = lambda_client.get_function(FunctionName=function_name)
    function = res["Configuration"]
    res = lambda_client.list_tags(Resource=function["FunctionArn"])
    function["Tags"] = res.get("Tags", {})

    start_lambda_function(function)


def stop_lambda_functions_by_tags(tags: dict):
    functions = get_lambda_functions_with_concurrency_by_tag(tags)
    for f in functions:
        stop_lambda_function(f)


def start_lambda_functions_by_tags(tags: dict):
    functions = get_lambda_functions_with_concurrency_by_tag(tags)
    for f in functions:
        start_lambda_function(f)


def stop_lambda_functions_by_schedule(current_hour: int, current_weekday: int):
    current_hour = str(current_hour)
    current_weekday = str(current_weekday)

    functions = get_lambda_functions_with_concurrency_by_tag({"AutoStopTime": current_hour})
    # Check day of the week matches
    target_functions = []
    for f in functions:
        weekdays_str = f["Tags"].get("AutoStopWeekday")
        if weekdays_str:
            weekdays = weekdays_str.split()
            if current_weekday not in weekdays:
                continue
        target_functions.append(f)

    if target_functions:
        logger.info(f"stopping {len(target_functions)} functions")
    else:
        logger.info("no function to stop")
    for f in target_functions:
        stop_lambda_function(f)


def start_lambda_functions_by_schedule(current_hour: int, current_weekday: int):
    current_hour = str(current_hour)
    current_weekday = str(current_weekday)

    functions = get_lambda_functions_with_concurrency_by_tag({"AutoStartTime": current_hour})
    # Check day of the week matches
    target_functions = []
    for f in functions:
        weekdays_str = f["Tags"].get("AutoStartWeekday")
        if weekdays_str:
            weekdays = weekdays_str.split()
            if current_weekday not in weekdays:
                continue
        target_functions.append(f)

    if target_functions:
        logger.info(f"starting {len(target_functions)} functions")
    else:
        logger.info("no function to start")
    for f in target_functions:
        start_lambda_function(f)


def stop_lambda_function(function):
    stopped_concurrency = int(function["Tags"].get("AutoStopConcurrency", 0))
    if function["AllocatedProvisionedConcurrentExecutions"] <= stopped_concurrency:
        # Already stopped
        return

    logger.info(f"stopping function {function['FunctionName']}, concurrency: {stopped_concurrency}")

    # Save the current requested concurrency as a tag
    last_requested_concurrency = function["RequestedProvisionedConcurrentExecutions"]
    lambda_client.tag_resource(
        Resource=function["FunctionArn"],
        Tags={"LastRequestedConcurrency": str(last_requested_concurrency)},
    )

    # Stop lambda
    if stopped_concurrency == 0:
        lambda_client.delete_provisioned_concurrency_config(
            FunctionName=function["FunctionName"],
            Qualifier=function["Version"],
        )
    else:
        lambda_client.put_provisioned_concurrency_config(
            FunctionName=function["FunctionName"],
            Qualifier=function["Version"],
            ProvisionedConcurrentExecutions=stopped_concurrency,
        )


def start_lambda_function(function):
    requested_concurrency = int(function["Tags"].get("LastRequestedConcurrency", 1))
    if function["AllocatedProvisionedConcurrentExecutions"] >= requested_concurrency:
        # Already started
        return

    logger.info(f"starting function, name: {function['FunctionName']}, concurrency: {requested_concurrency}")
    # Remove the last requested concurrency tag
    lambda_client.untag_resource(Resource=function["FunctionArn"], TagKeys=["LastRequestedConcurrency"])
    # Start lambda
    lambda_client.put_provisioned_concurrency_config(
        FunctionName=function["FunctionName"],
        Qualifier=function["Version"],
        ProvisionedConcurrentExecutions=requested_concurrency,
    )


def get_lambda_functions_with_concurrency_by_tag(tags: dict):
    functions = []
    res = lambda_client.get_paginator("list_functions").paginate().build_full_result()
    all_functions = res["Functions"]
    for function in all_functions:
        # Get function versions
        res = (
            lambda_client.get_paginator("list_versions_by_function")
            .paginate(FunctionName=function["FunctionName"])
            .build_full_result()
        )
        latest_version = res["Versions"][-1]["Version"]
        if latest_version == "$LATEST":
            # Skip unpublished functions
            continue

        function["Version"] = latest_version

        # Get provisioned concurrency config
        try:
            res = lambda_client.get_provisioned_concurrency_config(
                FunctionName=function["FunctionName"], Qualifier=latest_version
            )
        except lambda_client.exceptions.ProvisionedConcurrencyConfigNotFoundException:
            res["RequestedProvisionedConcurrentExecutions"] = 0
            res["AvailableProvisionedConcurrentExecutions"] = 0
            res["AllocatedProvisionedConcurrentExecutions"] = 0

        function["RequestedProvisionedConcurrentExecutions"] = res["RequestedProvisionedConcurrentExecutions"]
        function["AvailableProvisionedConcurrentExecutions"] = res["AvailableProvisionedConcurrentExecutions"]
        function["AllocatedProvisionedConcurrentExecutions"] = res["AllocatedProvisionedConcurrentExecutions"]

        # Get function tags and check if all required tags are present
        res = lambda_client.list_tags(Resource=function["FunctionArn"])
        function_tags = res.get("Tags", {})
        tag_matches = all([function_tags.get(key) == value for key, value in tags.items()])
        if not tag_matches:
            # Skip functions without required tags
            continue

        function["Tags"] = function_tags

        functions.append(function)

    return functions


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


if __name__ == "__main__":
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt="%(asctime)s %(name)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

    # lambda_handler({"hour": 12, "weekday": 0}, {})
    # lambda_handler({"action": "start", "tags": {"Project": "vc-api"}}, {})
    # lambda_handler({"action": "start", "tags": {"Project": "vc-api", "Island": "02"}}, {})
    # lambda_handler({"action": "stop", "tags": {"Project": "vc-api"}}, {})
    # lambda_handler({"action": "stop", "tags": {"Project": "vc-api"}, {"Island": "01"}}, {})
