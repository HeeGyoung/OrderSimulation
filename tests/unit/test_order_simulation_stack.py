import json
from aws_cdk.assertions import Template, Match
from aws_cdk import core
from order_simulation.order_simulation_stack import OrderSimulationStack
# test git hub

def get_template():
    app = core.App()
    OrderSimulationStack(app, "order-simulation")
    return json.dumps(app.synth().get_stack("order-simulation").template)


STACK_TEMPLATE = get_template()
cdk_assertions = Template.from_string(STACK_TEMPLATE)


def test_sqs_queue_created():
    cdk_assertions.resource_count_is("AWS::SQS::Queue", 3)
    cdk_assertions.has_resource_properties("AWS::SQS::Queue", {"QueueName": "app_q"})
    cdk_assertions.has_resource_properties("AWS::SQS::Queue", {"QueueName": "web_q"})
    cdk_assertions.has_resource_properties("AWS::SQS::Queue", {"QueueName": "pos_q"})


def test_sns_topic_created():
    cdk_assertions.resource_count_is("AWS::SNS::Topic", 1)
    cdk_assertions.has_resource_properties("AWS::SNS::Topic", {"TopicName": "send_order"})

    cdk_assertions.resource_count_is("AWS::SNS::Subscription", 3)
    cdk_assertions.has_resource_properties(
        "AWS::SNS::Subscription",
        {
            "FilterPolicy": {
                "send_restaurant_app": ["true"]
            }
        }
    )
    cdk_assertions.has_resource_properties(
        "AWS::SNS::Subscription",
        {
            "FilterPolicy": {
                "send_restaurant_web": ["true"]
            }
        }
    )
    cdk_assertions.has_resource_properties(
        "AWS::SNS::Subscription",
        {
            "FilterPolicy": {
                "send_restaurant_pos": ["true"]
            }
        }
    )


def test_iam_lambda_sqs_role():
    cdk_assertions.resource_count_is("AWS::IAM::Role", 1)
    policy_prefix = ":iam::aws:policy/service-role/"
    cdk_assertions.has_resource_properties("AWS::IAM::Role",
                                           {
                                               "RoleName": "lambda-sqs-role",
                                               "ManagedPolicyArns": [
                                                   {
                                                       "Fn::Join": Match.array_with([Match.array_with(
                                                           [f"{policy_prefix}AWSLambdaSQSQueueExecutionRole"])])
                                                   },
                                                   {
                                                       "Fn::Join": Match.array_with([Match.array_with(
                                                           [f"{policy_prefix}AWSLambdaDynamoDBExecutionRole"])])
                                                   }
                                               ]
                                           }
                                           )
    cdk_assertions.resource_count_is("AWS::IAM::Policy", 1)
    cdk_assertions.has_resource_properties("AWS::IAM::Policy",
                                           {
                                               "PolicyDocument": {
                                                   "Statement": Match.array_with([
                                                       Match.object_like({
                                                           "Action": ["dynamodb:BatchWriteItem", "dynamodb:PutItem"]
                                                       })
                                                   ])
                                               }
                                           }
                                           )


def test_dynamodb_table_created():
    cdk_assertions.resource_count_is("AWS::DynamoDB::Table", 1)
    cdk_assertions.has_resource_properties("AWS::DynamoDB::Table", {"TableName": "OrderResult"})
    cdk_assertions.has_resource_properties("AWS::DynamoDB::Table",
                                           {"KeySchema": [
                                               {
                                                   "AttributeName": "order_id",
                                                   "KeyType": "HASH"
                                               }
                                           ]})


def test_lambda_created():
    cdk_assertions.resource_count_is("AWS::Lambda::LayerVersion", 1)
    cdk_assertions.has_resource_properties("AWS::Lambda::LayerVersion", {"LayerName": "layer_v1"})

    cdk_assertions.resource_count_is("AWS::Lambda::Function", 4)
    cdk_assertions.has_resource_properties("AWS::Lambda::Function", {"FunctionName": "integration_app"})
    cdk_assertions.has_resource_properties("AWS::Lambda::Function", {"FunctionName": "integration_web"})
    cdk_assertions.has_resource_properties("AWS::Lambda::Function", {"FunctionName": "integration_pos"})
    cdk_assertions.has_resource_properties("AWS::Lambda::Function", {"FunctionName": "order_result_stream"})

    cdk_assertions.resource_count_is("AWS::Lambda::EventSourceMapping", 4)
    target_q = [k for k, v in json.loads(STACK_TEMPLATE)['Resources'].items()
                if v.get("Type", None) == "AWS::SQS::Queue"]
    assert len(target_q) == 3
    cdk_assertions.has_resource_properties("AWS::Lambda::EventSourceMapping",
                                           {
                                               "EventSourceArn":
                                                   {"Fn::GetAtt": Match.array_with([target_q[0]])}
                                           }
                                           )
    cdk_assertions.has_resource_properties("AWS::Lambda::EventSourceMapping",
                                           {
                                               "EventSourceArn":
                                                   {"Fn::GetAtt": Match.array_with([target_q[1]])}
                                           }
                                           )
    cdk_assertions.has_resource_properties("AWS::Lambda::EventSourceMapping",
                                           {
                                               "EventSourceArn":
                                                   {"Fn::GetAtt": Match.array_with([target_q[2]])}
                                           }
                                           )
    target_table = [k for k, v in json.loads(STACK_TEMPLATE)['Resources'].items()
                    if v.get("Type", None) == "AWS::DynamoDB::Table"]
    assert len(target_table) == 1
    cdk_assertions.has_resource_properties("AWS::Lambda::EventSourceMapping",
                                           {
                                               "EventSourceArn":
                                                   {"Fn::GetAtt": Match.array_with([target_table[0]])}
                                           }
                                           )


def test_api_gateway_created():
    cdk_assertions.resource_count_is("AWS::ApiGateway::RestApi", 1)
    cdk_assertions.has_resource_properties("AWS::ApiGateway::RestApi", {"Name": "order_result"})

    parent_api_gw = [k for k, v in json.loads(STACK_TEMPLATE)['Resources'].items() if
                     v.get("Type", None) == "AWS::ApiGateway::RestApi"]
    assert len(parent_api_gw) == 1
    cdk_assertions.resource_count_is("AWS::ApiGateway::Resource", 3)
    cdk_assertions.has_resource_properties("AWS::ApiGateway::Resource",
                                           {
                                               "PathPart": "app",
                                               "ParentId": {
                                                   "Fn::GetAtt": Match.array_with([parent_api_gw[0]])
                                               }
                                           })
    cdk_assertions.has_resource_properties("AWS::ApiGateway::Resource",
                                           {
                                               "PathPart": "web",
                                               "ParentId": {
                                                   "Fn::GetAtt": Match.array_with([parent_api_gw[0]])
                                               }
                                           })
    cdk_assertions.has_resource_properties("AWS::ApiGateway::Resource",
                                           {
                                               "PathPart": "pos",
                                               "ParentId": {
                                                   "Fn::GetAtt": Match.array_with([parent_api_gw[0]])
                                               }
                                           })
