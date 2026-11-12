import json
import os
import boto3
from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

s3 = boto3.client("s3")
BUCKET = os.environ["BACKUP_BUCKET"]

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
}


def _response(status, body):
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(body)}


def _build_pdf(txt_objects):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Deleted Orders Summary", styles["Title"]),
        Paragraph(
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]
    if not txt_objects:
        story.append(Paragraph("No deleted orders found.", styles["Normal"]))
    else:
        for key, content in txt_objects:
            story.append(Paragraph(f"<b>{key}</b>", styles["Heading3"]))
            for line in content.splitlines():
                story.append(Paragraph(line.replace(" ", "&nbsp;"), styles["Code"]))
            story.append(Spacer(1, 12))
    doc.build(story)
    return buf.getvalue()


def lambda_handler(event, context):
    """
    Lists every TXT file under `backups/` in S3, builds a single PDF
    summary of all deleted orders, uploads the PDF to S3 under
    `reports/`, and returns a pre-signed download URL in the response.

    Called by:
      - GET /reports/deleted-pdf  (on-demand)
      - EventBridge Scheduler     (scheduled_pdf wrapper)
    """
    try:
        paginator = s3.get_paginator("list_objects_v2")
        txt_files = []
        for page in paginator.paginate(Bucket=BUCKET, Prefix="backups/"):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".txt"):
                    body = s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read().decode("utf-8")
                    txt_files.append((obj["Key"], body))

        pdf_bytes = _build_pdf(txt_files)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        key = f"reports/summary-{ts}.pdf"
        s3.put_object(Bucket=BUCKET, Key=key, Body=pdf_bytes, ContentType="application/pdf")

        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=3600,
        )
        return _response(200, {"url": url, "key": key, "count": len(txt_files)})
    except Exception as e:
        return _response(500, {"error": str(e)})
