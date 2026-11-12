import json
import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
GSI_NAME = os.environ.get("GSI_NAME", "creation_date-index")

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
        resp = table.query(
            IndexName=GSI_NAME,
            KeyConditionExpression=Key("entity").eq("ORDER"),
            ScanIndexForward=True,
        )
        items = resp.get("Items", [])
        return _response(200, {"count": len(items), "orders": items})
    except Exception as e:
        return _response(500, {"error": str(e)})
