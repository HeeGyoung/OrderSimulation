#!/usr/bin/env python3

from aws_cdk import core

from order_simulation.order_simulation_stack import OrderSimulationStack


app = core.App()
OrderSimulationStack(app, "order-simulation")

app.synth()
