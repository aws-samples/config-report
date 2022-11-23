#!/usr/bin/env python3
import os

import aws_cdk as cdk

from config_report_stack import ConfigReport


app = cdk.App()
ConfigReport(app, "ConfigReport",
    
    )

app.synth()
