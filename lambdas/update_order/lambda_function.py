import json
import os
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
        order_id = event["pathParameters"]["id"]
        body = json.loads(event.get("body") or "{}")

        existing = table.get_item(Key={"order_id": order_id}).get("Item")
        if not existing:
            return _response(404, {"error": "Order not found"})

        update_expr = ["#lm = :lm"]
        expr_names = {"#lm": "last_modified"}
        expr_values = {":lm": datetime.now(timezone.utc).isoformat()}

        if "price" in body:
            update_expr.append("#p = :p")
            expr_names["#p"] = "price"
            expr_values[":p"] = Decimal(str(body["price"]))
        if "description" in body:
            update_expr.append("#d = :d")
            expr_names["#d"] = "description"
            expr_values[":d"] = body["description"]

        resp = table.update_item(
            Key={"order_id": order_id},
            UpdateExpression="SET " + ", ".join(update_expr),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )
        return _response(200, {"message": "Order updated", "order": resp["Attributes"]})
    except Exception as e:
        return _response(500, {"error": str(e)})
