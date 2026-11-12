"""
Generate the AWS architecture diagram for the Order Management System.

Usage (from the docs/ folder):
    pip install matplotlib
    python build_diagram.py

Output:
    images/architecture.png
"""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).parent / "images" / "architecture.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

# === Colors ===
C_CLIENT = "#7e57c2"   # purple
C_API    = "#ef5350"   # red
C_LAMBDA = "#fb8c00"   # orange
C_DATA   = "#1e88e5"   # blue
C_EVENT  = "#43a047"   # green
C_FREE   = "#ffb300"   # amber (freestyle)

fig, ax = plt.subplots(figsize=(16, 11))
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")


def box(x, y, w, h, label, color, text_color="white", fontsize=9, bold=True):
    fb = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.3,rounding_size=1.2",
        linewidth=1.2, edgecolor="black", facecolor=color, alpha=0.95,
    )
    ax.add_patch(fb)
    ax.text(
        x + w / 2, y + h / 2, label,
        ha="center", va="center", fontsize=fontsize, color=text_color,
        weight="bold" if bold else "normal",
    )


def arrow(x1, y1, x2, y2, color="#37474f", style="-|>", lw=1.4, label=None, label_offset=(0, 0)):
    ar = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style, mutation_scale=15,
        color=color, linewidth=lw,
    )
    ax.add_patch(ar)
    if label:
        ax.text(
            (x1 + x2) / 2 + label_offset[0],
            (y1 + y2) / 2 + label_offset[1],
            label,
            ha="center", fontsize=7.5, color=color, style="italic",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8),
        )


# === Title ===
ax.text(50, 97, "Order Management System  |  AWS Serverless Architecture",
        ha="center", fontsize=16, weight="bold")
ax.text(50, 94, "Region us-east-1 · fully serverless",
        ha="center", fontsize=10, style="italic", color="gray")

# === Layer 1: Client ===
box(38, 84, 24, 5, "Browser  ⇄  AWS Amplify Hosting\n(HTML / CSS / JS in client/)", C_CLIENT)

# === Layer 2: API Gateway (wide enough to span all 9 Lambdas below) ===
box(2, 72, 96, 6, "Amazon API Gateway (REST, stage: prod)\nhttps://<api-id>.execute-api.us-east-1.amazonaws.com/prod",
    C_API, fontsize=9)
arrow(50, 84, 50, 78, label="HTTPS / CORS", label_offset=(8, 0))

# === Layer 3: Lambda functions (left to right, three groups) ===
# Orders CRUD (5)
lambdas_crud = [
    "oms-create-order\nPOST /orders",
    "oms-get-all-orders\nGET /orders",
    "oms-get-order\nGET /orders/{id}",
    "oms-update-order\nPUT /orders/{id}",
    "oms-delete-order\nDELETE /orders/{id}",
]
crud_x_start = 2
for i, name in enumerate(lambdas_crud):
    box(crud_x_start + i * 9.4, 56, 8.6, 8, name, C_LAMBDA, fontsize=6.8)
    arrow(crud_x_start + i * 9.4 + 4.3, 72, crud_x_start + i * 9.4 + 4.3, 64, lw=0.9)

# Subscriptions (2)
sub_x = 53
for i, name in enumerate(["oms-subscribe\nPOST /subscriptions", "oms-unsubscribe\nDELETE /subscriptions"]):
    box(sub_x + i * 9.4, 56, 8.6, 8, name, C_LAMBDA, fontsize=6.8)
    arrow(sub_x + i * 9.4 + 4.3, 72, sub_x + i * 9.4 + 4.3, 64, lw=0.9)

# Reports (2)
rep_x = 73
for i, name in enumerate(["oms-generate-pdf\nGET /reports/deleted-pdf\n(uses reportlab layer)", "oms-list-reports\nGET /reports/scheduled"]):
    box(rep_x + i * 9.4, 56, 8.6, 8, name, C_LAMBDA, fontsize=6.2)
    arrow(rep_x + i * 9.4 + 4.3, 72, rep_x + i * 9.4 + 4.3, 64, lw=0.9)

# === Layer 4: Data services ===
# DynamoDB
box(4, 38, 22, 8,
    "Amazon DynamoDB\nTable: orders\nPK: order_id (UUID)\nGSI: creation_date-index",
    C_DATA, fontsize=8)

# SNS
box(55, 38, 18, 8,
    "Amazon SNS\nTopic: oms-order-deleted\nEmail subscribers",
    C_DATA, fontsize=8)

# S3
box(76, 38, 22, 8,
    "Amazon S3\nBucket: oms-backups-…\nbackups/ + reports/",
    C_DATA, fontsize=8)

# Connections: CRUD lambdas → DynamoDB
for i in range(5):
    arrow(crud_x_start + i * 9.4 + 4.3, 56, 15, 46, lw=0.7, color="#90a4ae")

# Subscriptions → SNS
arrow(57.3, 56, 62, 46, lw=0.9, color="#90a4ae")
arrow(66.7, 56, 66, 46, lw=0.9, color="#90a4ae")

# Reports → S3  (generate-pdf reads TXT + writes PDF; list-reports only reads)
arrow(77.3, 56, 84, 46, lw=0.9, color="#90a4ae", style="<|-|>")
arrow(86.7, 56, 90, 46, lw=0.9, color="#90a4ae")

# === Layer 5: Event-driven async flow ===
# Stream handler
box(28, 22, 24, 8,
    "Lambda: oms-stream-handler\n(async, decoupled from DELETE API)",
    C_EVENT, fontsize=8)

# DynamoDB Streams arrow
arrow(15, 38, 30, 30, color=C_EVENT, lw=1.6,
      label="DynamoDB Stream\n(REMOVE event)", label_offset=(-7, 1))

# Stream handler → SNS
arrow(52, 26, 64, 38, color=C_EVENT, lw=1.2, label="publish")
# Stream handler → S3
arrow(52, 26, 80, 38, color=C_EVENT, lw=1.2, label="put TXT backup", label_offset=(6, 2))

# Email subscribers
box(55, 14, 18, 5, "[ @ ]  Email Subscribers", "#26a69a", fontsize=9)
arrow(64, 38, 64, 19, color="#26a69a", lw=1.0, label="email")

# === Layer 6: EventBridge freestyle ===
# EventBridge rule
box(2, 12, 22, 8,
    "Amazon EventBridge  |  FREESTYLE\nRule: oms-scheduled-pdf-rule\nSchedule: rate(1 hour)",
    C_FREE, text_color="black", fontsize=8)

# Scheduled PDF lambda
box(2, 0.5, 22, 7,
    "Lambda: oms-scheduled-pdf\n(uses reportlab layer)",
    C_LAMBDA, fontsize=8)

arrow(13, 12, 13, 7.5, color=C_FREE, lw=1.4, label="invoke")
# Scheduled-pdf reads TXT from S3 and writes PDF to S3 → bidirectional
arrow(24, 3.5, 87, 38, color=C_FREE, lw=1.0, style="<|-|>", label="read TXT / write scheduled PDF", label_offset=(15, 8))

# === Legend ===
legend_items = [
    (C_CLIENT, "Client / Hosting"),
    (C_API,    "API Gateway"),
    (C_LAMBDA, "Lambda functions"),
    (C_DATA,   "Data services"),
    (C_EVENT,  "Async event flow"),
    (C_FREE,   "Freestyle (EventBridge)"),
]
for i, (col, lab) in enumerate(legend_items):
    ax.add_patch(patches.Rectangle((83, 12 - i * 2), 1.5, 1.2, facecolor=col, edgecolor="black"))
    ax.text(85, 12.6 - i * 2, lab, fontsize=8, va="center")

# === IAM footer note ===
ax.text(
    50, -3,
    "All Lambda functions assume IAM role: oms-lambda-role  "
    "(grants access to DynamoDB, S3, SNS, CloudWatch Logs, DynamoDB Streams)",
    ha="center", fontsize=9, style="italic", color="#37474f",
    bbox=dict(boxstyle="round,pad=0.4", fc="#eceff1", ec="#90a4ae", lw=0.8),
)

# Save
plt.tight_layout()
plt.savefig(OUT, dpi=180, bbox_inches="tight")
print(f"[OK] Diagram saved: {OUT}")
