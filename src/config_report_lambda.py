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

from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


today = datetime.now().strftime("%Y-%m-%d")  # Current day
filename = f'/tmp/Non_compliant_resources-{today}.csv'  # CSV report filename
AGGREGATOR_NAME = os.environ['AGGREGATOR_NAME']  # AWS Config Aggregator name
SENDER = os.environ['SENDER']  # SES Sender address
RECIPIENT = os.environ['RECIPIENT']  # SES Recipient address

    

# Generate the resource link to AWS Console UI
def get_link(aws_region, resource_id, resource_type):
    return f'https://{aws_region}.console.aws.amazon.com/config/home?region={aws_region}#/resources/timeline?resourceId={resource_id}&resourceType={resource_type}'

# Generate the AWS Config report email 
def send_email(today, SENDER, RECIPIENT, filename):
    # The subject line for the email.
    SUBJECT = f"AWS Config non-compliant resources report {today}"
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
    c = 0
    non_compliant_resources = []
    # Get list of non compliant resources.
    for rules in response.get("AggregateComplianceByConfigRules", []):
        rule_name = rules["ConfigRuleName"]
        rule_region = rules["AwsRegion"]
        account_id = rules["AccountId"]
        region_client = boto3.client("config", region_name=rule_region)
        response = region_client.get_compliance_details_by_config_rule(
            ConfigRuleName=rule_name,
            ComplianceTypes=['NON_COMPLIANT'])
      
        # For each non-compliant resource, note the ResultRecordedTime.
        for eval_results in response.get("EvaluationResults", []):
            eval_results_id = eval_results.get("EvaluationResultIdentifier", {})
            result_qualifier = eval_results_id.get("EvaluationResultQualifier", {})
            resource_type = result_qualifier.get("ResourceType", None)
            resource_id = result_qualifier.get("ResourceId", None)
            if resource_id!=None and resource_type!=None:
                response = region_client.get_compliance_details_by_resource(
                    ResourceType=resource_type,
                    ResourceId=resource_id,
                    ComplianceTypes=['NON_COMPLIANT']
                )

                
                resources_info = response.get("EvaluationResults", [])
                for resource_info in resources_info:    
                
                    recorded_time = resource_info.get("ResultRecordedTime", None)
                    compliance_type = resource_info.get("ComplianceType", None)
                    
                    # Is the Recorded time more than 30 days in past?.
                    if recorded_time==None:
                        raise RuntimeError("recorded time invalid")
    
                    today_minus_30 = datetime.now() - timedelta(days=30)
    
                    if recorded_time.timestamp() < today_minus_30.timestamp():
                        details = resource_info.get("EvaluationResultIdentifier", {})\
                        .get("EvaluationResultQualifier", {})
                        
                        details["ComplianceType"] = compliance_type
                        details["ResultRecordedTime"] = recorded_time
                        details["Region"] = rule_region
                        details["AccountId"] = account_id
                        details["Link"] = get_link(rule_region, details["ResourceId"], details["ResourceType"])
                        
                        non_compliant_resources.append(details)
    if len(non_compliant_resources) > 0:
    # Create and save the report in temporary folder to send.
        create_and_save_report(non_compliant_resources)
        send_email(today, SENDER, RECIPIENT, filename="/tmp/ConfigReport.csv")
    else:
        print("No non compliant resources available")
                
                

def create_and_save_report(non_compliant_resources, filename="/tmp/ConfigReport.csv"):
    
    fieldnames = non_compliant_resources[0].keys()
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in non_compliant_resources:
            writer.writerow(row)
    print("Report generated " + filename)
    import os
    print(os.listdir("/tmp/"))
        