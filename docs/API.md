# API reference

`<API>` is your API Gateway invoke URL, e.g. `https://abc123.execute-api.us-east-1.amazonaws.com/prod`.

| API Name | Method | URL | Sample Input | Sample Output |
|---|---|---|---|---|
| Create Order | POST | `<API>/orders` | `{ "description": "Wireless headphones", "price": 129.99 }` | `{ "message": "Order created", "order": { "order_id": "8e2f...", "entity": "ORDER", "description": "Wireless headphones", "price": 129.99, "creation_date": "2026-05-23T10:00:00+00:00", "last_modified": "2026-05-23T10:00:00+00:00" } }` |
| Get All Orders (sorted by creation date) | GET | `<API>/orders` | _(no body, no params)_ | `{ "count": 2, "orders": [ { "order_id": "...", "description": "Order A", "price": 50, "creation_date": "2026-05-23T09:00:00+00:00", ... }, { "order_id": "...", "description": "Order B", "price": 75, "creation_date": "2026-05-23T10:00:00+00:00", ... } ] }` |
| Get Single Order | GET | `<API>/orders/{id}` — e.g. `<API>/orders/8e2f...` | _(no body)_ | `{ "order": { "order_id": "8e2f...", "description": "Wireless headphones", "price": 129.99, ... } }` |
| Update Order | PUT | `<API>/orders/{id}` | `{ "description": "Wireless headphones (updated)", "price": 119.99 }` | `{ "message": "Order updated", "order": { "order_id": "8e2f...", "description": "Wireless headphones (updated)", "price": 119.99, "last_modified": "2026-05-23T10:15:00+00:00", ... } }` |
| Delete Order | DELETE | `<API>/orders/{id}` | _(no body)_ | `{ "message": "Order deleted", "order_id": "8e2f..." }` |
| Subscribe Email to Notifications | POST | `<API>/subscriptions` | `{ "email": "you@example.com" }` | `{ "message": "Subscription requested. Please check your inbox and confirm.", "subscription_arn": "pending confirmation" }` |
| Unsubscribe Email | DELETE | `<API>/subscriptions` | `{ "email": "you@example.com" }` | `{ "message": "Unsubscribed", "removed": ["arn:aws:sns:..."] }` |
| Generate Deleted-Orders PDF | GET | `<API>/reports/deleted-pdf` | _(no body)_ | `{ "url": "https://oms-backups-XXX.s3.amazonaws.com/reports/summary-20260523T101500Z.pdf?X-Amz-...", "key": "reports/summary-20260523T101500Z.pdf", "count": 3 }` |
| List Auto-Generated Reports | GET | `<API>/reports/scheduled` | _(no body)_ | `{ "count": 4, "reports": [ { "key": "reports/scheduled/auto-20260523T101500Z.pdf", "last_modified": "2026-05-23T10:15:02+00:00", "size_bytes": 2143, "url": "https://...presigned..." }, ... ] }` |

---

## Test flows

1. **Create order →** Open client, create an order with description and price → orders table shows the new row.
2. **Update order →** Use the Update Order form with the order_id → orders table refreshes with new price.
3. **Get all orders (sorted) →** Create 3 orders a few seconds apart → click Refresh → confirm they appear ordered by creation_date ascending.
4. **Subscribe →** Submit your email → check inbox → click AWS SNS confirmation link.
5. **Delete order + notification →** Delete an order from the orders table → within seconds, an email arrives with the order's details.
6. **Verify backup →** Open the S3 console → `oms-backups-<ACCOUNT_ID>/backups/` → confirm a TXT file exists for the deleted order.
7. **Generate PDF report →** PDF Report tab → click Generate PDF → click the download link → PDF opens with every deleted order listed.
8. **EventBridge auto-reports →** Open Scheduled Reports tab → click Refresh → multiple auto-generated PDFs appear (paginated, 10 at a time); wait one hour, refresh, a new one appears.
9. **Unsubscribe →** Submit your email under Unsubscribe → confirm a follow-up delete of an order does NOT email you.
