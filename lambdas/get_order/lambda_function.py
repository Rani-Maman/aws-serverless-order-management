import json
import os
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
}


def _response(status, body):
    return {
        "statusCode": status,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, default=str),
    }


def lambda_handler(event, context):
    try:
        order_id = event["pathParameters"]["id"]
        resp = table.get_item(Key={"order_id": order_id})
        item = resp.get("Item")
        if not item:
            return _response(404, {"error": "Order not found"})
        return _response(200, {"order": item})
    except Exception as e:
        return _response(500, {"error": str(e)})
