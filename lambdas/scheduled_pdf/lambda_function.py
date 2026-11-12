import os
import boto3
from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

s3 = boto3.client("s3")
BUCKET = os.environ["BACKUP_BUCKET"]


def _build_pdf(txt_objects):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Deleted Orders Summary (Scheduled)", styles["Title"]),
        Paragraph(
            f"Generated automatically by EventBridge: {datetime.now(timezone.utc).isoformat()}",
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
    Invoked by EventBridge Scheduler on a recurring schedule
    (e.g. every 5 minutes during demo, or daily in production).

    Builds the same PDF summary as the on-demand generate_pdf Lambda
    but writes it under `reports/scheduled/` with a timestamped filename,
    so the client UI can list all auto-generated reports separately.
    """
    paginator = s3.get_paginator("list_objects_v2")
    txt_files = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix="backups/"):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".txt"):
                body = s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read().decode("utf-8")
                txt_files.append((obj["Key"], body))

    pdf_bytes = _build_pdf(txt_files)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"reports/scheduled/auto-{ts}.pdf"
    s3.put_object(Bucket=BUCKET, Key=key, Body=pdf_bytes, ContentType="application/pdf")
    return {"key": key, "count": len(txt_files)}
