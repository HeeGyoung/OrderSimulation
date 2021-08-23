from pathlib import Path
from aws_cdk import (
    aws_iam as iam,
    aws_sqs as sqs,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_lambda_event_sources as sources,
    core
)
ROOT_DIR = Path(__file__).parent.parent.absolute()


class OrderSimulationStack(core.Stack):
    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # 1. create sqs for order sns subscription
        app_q = sqs.Queue(self, "app_q", queue_name="app_q", visibility_timeout=core.Duration.seconds(30))
        web_q = sqs.Queue(self, "web_q", queue_name="web_q", visibility_timeout=core.Duration.seconds(30))
        pos_q = sqs.Queue(self, "pos_q", queue_name="pos_q", visibility_timeout=core.Duration.seconds(30))

        # 2. create sns for publish order
        topic = sns.Topic(self, "send_order", topic_name="send_order")
        subscript_filter = sns.SubscriptionFilter.string_filter(allowlist=["true"])
        topic.add_subscription(subs.SqsSubscription(
            queue=app_q, filter_policy={"send_restaurant_app": subscript_filter}))
        topic.add_subscription(subs.SqsSubscription(
            queue=web_q, filter_policy={"send_restaurant_web": subscript_filter}))
        topic.add_subscription(subs.SqsSubscription(
            queue=pos_q, filter_policy={"send_restaurant_pos": subscript_filter}))

        # 3. create trigger lambda for sqs
        lambda_sqs_role = iam.Role(
            self, "lambda-sqs-role", role_name="lambda-sqs-role", description="lambda trigger - sqs",
            assumed_by=iam.ServicePrincipal(service="lambda"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    managed_policy_name="service-role/AWSLambdaSQSQueueExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    managed_policy_name="service-role/AWSLambdaDynamoDBExecutionRole")
            ]
        )
        layer = _lambda.LayerVersion(
            self, "layer", layer_version_name="layer_v1", compatible_runtimes=[_lambda.Runtime.PYTHON_3_8],
            code=_lambda.Code.from_asset(f"{ROOT_DIR}/lambda_layer")
        )

        integration_app = _lambda.Function(
            self, "integration_app", function_name="integration_app",
            runtime=_lambda.Runtime.PYTHON_3_8, code=_lambda.Code.asset(f"{ROOT_DIR}/lambda"),
            handler="integration.handler", layers=[layer], role=lambda_sqs_role
        )
        _lambda.EventSourceMapping(
            self, "qpp_q_trigger", target=integration_app, batch_size=10, event_source_arn=app_q.queue_arn
        )

        integration_web = _lambda.Function(
            self, "integration_web", function_name="integration_web",
            runtime=_lambda.Runtime.PYTHON_3_8, code=_lambda.Code.asset(f"{ROOT_DIR}/lambda"),
            handler="integration.handler", layers=[layer], role=lambda_sqs_role
        )
        _lambda.EventSourceMapping(
            self, "web_q_trigger", target=integration_web, batch_size=10, event_source_arn=web_q.queue_arn
        )

        integration_pos = _lambda.Function(
            self, "integration_pos", function_name="integration_pos",
            runtime=_lambda.Runtime.PYTHON_3_8, code=_lambda.Code.asset(f"{ROOT_DIR}/lambda"),
            handler="integration.handler", layers=[layer], role=lambda_sqs_role
        )
        _lambda.EventSourceMapping(
            self, "pos_q_trigger", target=integration_pos, batch_size=10, event_source_arn=pos_q.queue_arn
        )

        # 4. create api gateway to invoke lambda from external
        order_result_api = apigw.RestApi(self, "order_result", rest_api_name="order_result",
                                         cloud_watch_role=False, deploy=False)
        app_api = order_result_api.root.add_resource("app")
        app_api.add_method("POST", apigw.LambdaIntegration(handler=integration_app, proxy=True))

        web_api = order_result_api.root.add_resource("web")
        web_api.add_method("POST", apigw.LambdaIntegration(handler=integration_web, proxy=True))

        pos_api = order_result_api.root.add_resource("pos")
        pos_api.add_method("POST", apigw.LambdaIntegration(handler=integration_pos, proxy=True))

        # 5. create dynamodb to insert order result
        order_result = dynamodb.Table(
            self, "OrderResult", table_name="OrderResult",
            partition_key=dynamodb.Attribute(name="order_id", type=dynamodb.AttributeType.NUMBER),
            stream=dynamodb.StreamViewType.NEW_IMAGE
        )
        integration_app.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:BatchWriteItem", "dynamodb:PutItem"],
                effect=iam.Effect.ALLOW,
                resources=[order_result.table_arn]
            )
        )

        # 6. create trigger lambda for dynamodb stream
        order_result_stream = _lambda.Function(
            self, "order_result_stream", function_name="order_result_stream",
            runtime=_lambda.Runtime.PYTHON_3_8, code=_lambda.Code.asset(f"{ROOT_DIR}/lambda"),
            handler="db_stream_check.handler", layers=[layer], role=lambda_sqs_role
        )
        order_result_stream.add_event_source(
            sources.DynamoEventSource(
                table=order_result,
                starting_position=_lambda.StartingPosition.TRIM_HORIZON
            )
        )
