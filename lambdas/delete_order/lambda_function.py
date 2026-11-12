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
    """
    Deletes an order from DynamoDB.

    The deletion triggers a DynamoDB Stream REMOVE event, which is consumed
    asynchronously by the stream_handler Lambda. That handler is responsible
    for (a) writing a TXT backup to S3 and (b) publishing an SNS notification
    to subscribed users.

    This function does NOT wait for the backup or notification — it returns
    immediately once the row is removed from DynamoDB. The user-facing
    delete operation is therefore a single, fast action.
    """
    try:
        order_id = event["pathParameters"]["id"]

        existing = table.get_item(Key={"order_id": order_id}).get("Item")
        if not existing:
            return _response(404, {"error": "Order not found"})

        table.delete_item(Key={"order_id": order_id})

        return _response(200, {
            "message": "Order deleted",
            "order_id": order_id,
        })
    except Exception as e:
        return _response(500, {"error": str(e)})
