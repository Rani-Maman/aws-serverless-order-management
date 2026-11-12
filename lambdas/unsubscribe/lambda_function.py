import json
import os
import boto3

sns = boto3.client("sns")
TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
}


def _response(status, body):
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(body)}


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        email = body.get("email")
        if not email:
            return _response(400, {"error": "email is required"})

        paginator = sns.get_paginator("list_subscriptions_by_topic")
        removed = []
        for page in paginator.paginate(TopicArn=TOPIC_ARN):
            for sub in page.get("Subscriptions", []):
                if sub.get("Endpoint") == email and sub.get("SubscriptionArn", "").startswith("arn:"):
                    sns.unsubscribe(SubscriptionArn=sub["SubscriptionArn"])
                    removed.append(sub["SubscriptionArn"])

        if not removed:
            return _response(404, {"error": "No confirmed subscription found for this email"})
        return _response(200, {"message": "Unsubscribed", "removed": removed})
    except Exception as e:
        return _response(500, {"error": str(e)})
