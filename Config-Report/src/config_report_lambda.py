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

import json
import boto3
import os
from distutils.command.config import config
from datetime import datetime, timedelta
import json
import csv
import logging


from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


today = datetime.now().strftime("%Y-%m-%d")  # Current day
AGGREGATOR_NAME = os.environ['AGGREGATOR_NAME']  # AWS Config Aggregator name
SENDER = os.environ['SENDER']  # SES Sender address
RECIPIENT = os.environ['RECIPIENT']  # SES Recipient address
Organization = os.environ['Organization']  # Identity Solutions org
filename = f'/tmp/Non_compliant_resources-{Organization}-{today}.csv'  # CSV report filename

    

# Generate the resource link to AWS Console UI
def get_link(aws_region, resource_id, resource_type):
    return f'https://{aws_region}.console.aws.amazon.com/config/home?region={aws_region}#/resources/timeline?resourceId={resource_id}&resourceType={resource_type}'

# Generate the AWS Config report email 
def send_email(Organization, today, SENDER, RECIPIENT, filename):
    # The subject line for the email.
    SUBJECT = f"AWS Config non-compliant resources report in {Organization} {today}"
    ATTACHMENT = filename
    BODY_TEXT = "Hello,\r\nPlease see the attached file for the list of resources which have been non-compliant for more than 30 days."
    ses = boto3.client('ses')

    # The HTML body of the email.
    BODY_HTML = """\
    <html>
    <head></head>
    <body>
    <p>Hello, please see the attached file for the list of resources which have been non-compliant for more than 30 days</p>
    </body>
    </html>
    """
    CHARSET = "utf-8"
    msg = MIMEMultipart('mixed')
    msg['Subject'] = SUBJECT
    msg['From'] = SENDER
    msg['To'] = RECIPIENT
    msg_body = MIMEMultipart('alternative')
    textpart = MIMEText(BODY_TEXT.encode(CHARSET), 'plain', CHARSET)
    htmlpart = MIMEText(BODY_HTML.encode(CHARSET), 'html', CHARSET)
    msg_body.attach(textpart)
    msg_body.attach(htmlpart)
    att = MIMEApplication(open(ATTACHMENT, 'rb').read())
    att.add_header('Content-Disposition', 'attachment',
                   filename=os.path.basename(ATTACHMENT))
    msg.attach(msg_body)
    msg.attach(att)
    # Provide the contents of the email.
    response = ses.send_raw_email(
        Source=SENDER,
        Destinations=[
            RECIPIENT
        ],
        RawMessage={
            'Data': msg.as_string(),
        }
    )
    print("Email sent! Message ID:"),
    print(response['MessageId'])
    

# Get the list of non compliant resources.
def config_reporter(event, context):
    client = boto3.client("config")
    # Get the non compliant rules for aggregator.
    paginator = client.get_paginator('describe_aggregate_compliance_by_config_rules')
    response = client.describe_aggregate_compliance_by_config_rules(
        ConfigurationAggregatorName=AGGREGATOR_NAME,
        Filters={'ComplianceType': 'NON_COMPLIANT'}
        )
    
    
    non_compliant_resources = []
    
    for rules in response.get("AggregateComplianceByConfigRules", []):
        rule_name = rules["ConfigRuleName"]
        rule_region = rules["AwsRegion"]
        account_id = rules["AccountId"]
        
        # Get list of non compliant resources.    
        response = client.get_aggregate_compliance_details_by_config_rule(
            ConfigurationAggregatorName=AGGREGATOR_NAME,
            ConfigRuleName=rule_name,
            AccountId=account_id,
            AwsRegion=rule_region,
            ComplianceType='NON_COMPLIANT'
        )
        
        
        for eval_results in response.get("AggregateEvaluationResults", []):
            eval_results_id = eval_results.get("EvaluationResultIdentifier", {})
            result_qualifier = eval_results_id.get("EvaluationResultQualifier", {})
            result_qualifier["ComplianceType"] = eval_results.get("ComplianceType", None)
            result_qualifier["ResultRecordedTime"] = eval_results.get("ResultRecordedTime", None)
            result_qualifier["AccountId"] = eval_results.get("AccountId", None)
            result_qualifier["AwsRegion"] = eval_results.get("AwsRegion", None)
            
            if result_qualifier["ResultRecordedTime"]==None:
                raise RuntimeError("recorded time invalid")
            
            today_minus_30 = datetime.now() - timedelta(days=30)          
            
            if result_qualifier["ResultRecordedTime"].timestamp() < today_minus_30.timestamp():
                
                result_qualifier["Link"] = get_link(rule_region, 
                                            result_qualifier["ResourceId"], 
                                            result_qualifier["ResourceType"]
                                            )
                print("Non compliant resource: ", result_qualifier)
                non_compliant_resources.append(result_qualifier)

    if len(non_compliant_resources) > 0:
    # Create and save the report in temporary folder to send.
        create_and_save_report(non_compliant_resources)
        send_email(Organization, today, SENDER, RECIPIENT, filename=filename)
    else:
        print("No non compliant resources available")
                
                

def create_and_save_report(non_compliant_resources, filename=filename):
    
    fieldnames = non_compliant_resources[0].keys()
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in non_compliant_resources:
            writer.writerow(row)
    print("Report generated " + filename)
    import os
    print(os.listdir("/tmp/"))
