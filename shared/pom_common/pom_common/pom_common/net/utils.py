def user_agent_for_lambda(context):
    if context is None:
        context = {}

    unknown = 'unknown'

    function_name = getattr(context, "function_name", unknown)
    function_version = getattr(context, "function_version", unknown)
    aws_request_id = getattr(context, "aws_request_id", unknown)

    return f"Lambda/1.0 {function_name}/{function_version} (aws_request_id: {aws_request_id})"
