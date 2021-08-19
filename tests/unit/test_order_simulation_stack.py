import json
import pytest

from aws_cdk import core
from order_simulation.order_simulation_stack import OrderSimulationStack


def get_template():
    app = core.App()
    OrderSimulationStack(app, "order-simulation")
    return json.dumps(app.synth().get_stack("order-simulation").template)


def test_sqs_queue_created():
    assert("AWS::SQS::Queue" in get_template())


def test_sns_topic_created():
    assert("AWS::SNS::Topic" in get_template())
