"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT-0
Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

from typing_extensions import runtime
from async_timeout import timeout
from aws_cdk.aws_events import Rule, Schedule
from aws_cdk.aws_iam import Role
from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    triggers as triggers,
    aws_events_targets as targets,
    aws_logs as logs
)
import aws_cdk
from constructs import Construct


class ConfigReport(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        Aggregator = aws_cdk.CfnParameter(
            self,
            "Aggregator",
            type="String",
            default='aggregator',
            description="Name of AWS Config Aggregator"
        )

        Recipient = aws_cdk.CfnParameter(
            self,
            "Recipient",
            type="String",
            default='recipient@email.com',
            description="SES recipient email address"
        )
        Sender = aws_cdk.CfnParameter(
            self,
            "Sender",
            type="String",
            default='sender@email.com',
            description="SES sender email address"
        )
        Weekday = aws_cdk.CfnParameter(
            self,
            "Weekday",
            type="String",
            default='2',
            description="Day-of-week 1-7 or SUN-SAT Lambda will run. For example: for Monday, type 2"
        )
        Hour = aws_cdk.CfnParameter(
            self,
            "Hour",
            type="String",
            default='23',
            description="The time (hour) the Lambda will run. For example: for 23:50 UTC, type 23"
        )
        Minute = aws_cdk.CfnParameter(
            self,
            "Minute",
            type="String",
            default='50',
            description="The time (minute) the Lambda will run. For example: for 23:50 UTC, type 50"
        )
        SESarn = aws_cdk.CfnParameter(
            self,
            "SESarn",
            type="String",
            default='arn:aws:ses:us-east-1:888888888888:identity/example.com',
            description="The preconfigured SES arn, for example: arn:aws:ses:us-east-1:888888888888:identity/example.com"
        )
        config_reporter_lambda = _lambda.Function(self, "config_reporter",
                                                        log_retention=logs.RetentionDays.ONE_MONTH,
                                                        code=_lambda.Code.from_asset(
                                                            "../src/"),
                                                        runtime=_lambda.Runtime.PYTHON_3_8,
                                                        handler="config_report_lambda.config_reporter",
                                                        timeout=Duration.seconds(
                                                            300),
                                                        environment={
                                                            "AGGREGATOR_NAME": Aggregator.value_as_string,
                                                            "SENDER": Sender.value_as_string,
                                                            "RECIPIENT": Recipient.value_as_string}
                                                  )
        config_reporter_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                'ses:SendRawEmail'
            ],
            resources=[
                SESarn.value_as_string
                ],
            conditions={
                "ForAllValues:StringLike": {
                    "ses:Recipients": Recipient.value_as_string,
                },
                "StringLike": {
                    "ses:FromAddress": Sender.value_as_string
                }
            }

        ))

        config_reporter_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                'config:SelectAggregateResourceConfig',
                'config:GetComplianceDetailsByConfigRule',
                'config:GetComplianceDetailsByResource',
                'config:SelectAggregateResourceConfig',
                'config:DescribeAggregateComplianceByConfigRules'
            ],
            resources=[
                '*'
            ],
            conditions={
                "StringEquals": {
                    "aws:ResourceAccount": [aws_cdk.Aws.ACCOUNT_ID
                                            ]
                }
            }
        ))
        rule = Rule(self, "ConfigReporterCW",
                    schedule=Schedule.cron(
                       week_day=Weekday.value_as_string ,minute=Minute.value_as_string, hour=Hour.value_as_string)
                    )
        rule.add_target(targets.LambdaFunction(config_reporter_lambda))
        trigger = triggers.Trigger(
            self, "TriggerLambda", handler=config_reporter_lambda)