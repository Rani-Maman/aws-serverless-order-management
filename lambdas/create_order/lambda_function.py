import json
import os
import uuid
import boto3
from datetime import datetime, timezone
from decimal import Decimal

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
        body = json.loads(event.get("body") or "{}")
        price = body.get("price")
        description = body.get("description")

        if price is None or description is None:
            return _response(400, {"error": "price and description are required"})

        now = datetime.now(timezone.utc).isoformat()
        order_id = str(uuid.uuid4())

        item = {
            "order_id": order_id,
            "entity": "ORDER",
            "creation_date": now,
            "last_modified": now,
            "price": Decimal(str(price)),
            "description": description,
        }
        table.put_item(Item=item)
        return _response(201, {"message": "Order created", "order": item})
    except Exception as e:
        return _response(500, {"error": str(e)})
