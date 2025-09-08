import boto3

from function import lambda_handler, get_lambda_function_by_name

lambda_client = boto3.client("lambda")


def test_scheduled_start():
    lambda_handler({"hour": 10, "weekday": 0}, {})
    function = get_lambda_function_by_name("test")
    assert function["RequestedProvisionedConcurrentExecutions"] == 1


def test_scheduled_stop():
    lambda_handler({"hour": 11, "weekday": 0}, {})
    function = get_lambda_function_by_name("test")
    assert function["RequestedProvisionedConcurrentExecutions"] == 0


def test_start_by_name():
    lambda_handler({"action": "start", "function": "test"}, {})
    function = get_lambda_function_by_name("test")
    assert function["RequestedProvisionedConcurrentExecutions"] == 1


def test_stop_by_name():
    lambda_handler({"action": "stop", "function": "test"}, {})
    function = get_lambda_function_by_name("test")
    assert function["RequestedProvisionedConcurrentExecutions"] == 0


def test_start_by_tags():
    lambda_handler({"action": "start", "tags": {"Project": "test"}}, {})
    function = get_lambda_function_by_name("test")
    assert function["RequestedProvisionedConcurrentExecutions"] == 1


def test_stop_by_tags():
    lambda_handler({"action": "stop", "tags": {"Project": "test"}}, {})
    function = get_lambda_function_by_name("test")
    assert function["RequestedProvisionedConcurrentExecutions"] == 0


def teardown_module():
    function = get_lambda_function_by_name("test")
    lambda_client.delete_provisioned_concurrency_config(
        FunctionName=function["FunctionName"], Qualifier=function["Version"]
    )
