import json
import os
import boto3
from decimal import Decimal

s3 = boto3.client("s3")
sns = boto3.client("sns")

BUCKET = os.environ["BACKUP_BUCKET"]
TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]


def _deserialize(image):
    """Convert a DynamoDB stream image (low-level format) to a plain dict."""
    out = {}
    for k, v in image.items():
        if "S" in v:
            out[k] = v["S"]
        elif "N" in v:
            out[k] = float(v["N"])
        elif "BOOL" in v:
            out[k] = v["BOOL"]
        else:
            out[k] = str(v)
    return out


def lambda_handler(event, context):
    """
    Triggered by the DynamoDB stream on the `orders` table.
    For each REMOVE event:
      1. Writes a TXT backup of the deleted order to S3.
      2. Publishes the deleted order details to the SNS topic
         (subscribed emails receive the notification automatically).

    Runs asynchronously — the original DELETE API call has already
    returned to the client by the time this handler executes.
    """
    for record in event.get("Records", []):
        if record.get("eventName") != "REMOVE":
            continue

        old_image = record["dynamodb"].get("OldImage", {})
        order = _deserialize(old_image)
        order_id = order.get("order_id", "unknown")

        txt_body = (
            f"DELETED ORDER\n"
            f"=============\n"
            f"Order ID    : {order.get('order_id')}\n"
            f"Description : {order.get('description')}\n"
            f"Price       : {order.get('price')}\n"
            f"Created     : {order.get('creation_date')}\n"
            f"Last Modified: {order.get('last_modified')}\n"
        )
        s3.put_object(
            Bucket=BUCKET,
            Key=f"backups/{order_id}.txt",
            Body=txt_body.encode("utf-8"),
            ContentType="text/plain",
        )

        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject=f"Order Deleted: {order_id}",
            Message=txt_body,
        )

    return {"status": "ok"}
