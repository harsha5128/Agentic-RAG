# test_sqs.py

import boto3
import os
from dotenv import load_dotenv

load_dotenv()

sqs = boto3.client(
    "sqs",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

response = sqs.send_message(
    QueueUrl=os.getenv("AWS_SQS_QUEUE_URL"),
    MessageBody='{"file":"sample.pdf"}'
)

print(response)