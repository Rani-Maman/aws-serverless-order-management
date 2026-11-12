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

        resp = sns.subscribe(
            TopicArn=TOPIC_ARN,
            Protocol="email",
            Endpoint=email,
            ReturnSubscriptionArn=True,
        )
        return _response(200, {
            "message": "Subscription requested. Please check your inbox and confirm.",
            "subscription_arn": resp["SubscriptionArn"],
        })
    except Exception as e:
        return _response(500, {"error": str(e)})
