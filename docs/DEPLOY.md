# Deployment Runbook — Order Management System

Run these commands in **PowerShell** on Windows (AWS CLI v2 installed and `aws configure` done with credentials for your free-tier account, region `us-east-1`).

> Every command can be copied as-is. Names use the prefix `oms-` so they are easy to identify and clean up later.

---

## 0. Variables (run once per PowerShell session)

```powershell
$REGION       = "us-east-1"
$ACCOUNT_ID   = (aws sts get-caller-identity --query Account --output text)
$TABLE        = "orders"
$BUCKET       = "oms-backups-$ACCOUNT_ID"
$TOPIC        = "oms-order-deleted"
$ROLE_NAME    = "oms-lambda-role"
$API_NAME     = "oms-api"
```

---

## 1. Create the IAM role for all Lambdas

```powershell
# Trust policy
@'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
'@ | Out-File -Encoding ascii trust.json

aws iam create-role --role-name $ROLE_NAME --assume-role-policy-document file://trust.json

# Attach managed policies for DynamoDB, S3, SNS, CloudWatch logs
aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AWSLambdaBasicExecutionRole
aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AmazonSNSFullAccess
aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaDynamoDBExecutionRole

$ROLE_ARN = "arn:aws:iam::${ACCOUNT_ID}:role/$ROLE_NAME"
Start-Sleep -Seconds 10   # wait for IAM propagation
```

---

## 2. Create the DynamoDB table + GSI + Streams

```powershell
aws dynamodb create-table `
  --table-name $TABLE `
  --attribute-definitions `
      AttributeName=order_id,AttributeType=S `
      AttributeName=entity,AttributeType=S `
      AttributeName=creation_date,AttributeType=S `
  --key-schema AttributeName=order_id,KeyType=HASH `
  --billing-mode PAY_PER_REQUEST `
  --global-secondary-indexes "[{\"IndexName\":\"creation_date-index\",\"KeySchema\":[{\"AttributeName\":\"entity\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"creation_date\",\"KeyType\":\"RANGE\"}],\"Projection\":{\"ProjectionType\":\"ALL\"}}]" `
  --stream-specification StreamEnabled=true,StreamViewType=OLD_IMAGE

aws dynamodb wait table-exists --table-name $TABLE
$STREAM_ARN = (aws dynamodb describe-table --table-name $TABLE --query "Table.LatestStreamArn" --output text)
```

**Why this schema?**
- Partition key `order_id` (UUID) makes each order uniquely identifiable in O(1).
- GSI `creation_date-index` lets us run `Query` (not Scan) with a constant partition `entity="ORDER"` and `creation_date` as the sort key, so `GET /orders` returns items already sorted by creation date.
- Streams with `OLD_IMAGE` deliver the deleted row to the async handler so we can back it up and notify.

---

## 3. Create the S3 bucket

```powershell
aws s3api create-bucket --bucket $BUCKET --region $REGION
# Block all public access; we use presigned URLs.
aws s3api put-public-access-block --bucket $BUCKET --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

---

## 4. Create the SNS topic

```powershell
$TOPIC_ARN = (aws sns create-topic --name $TOPIC --query TopicArn --output text)
```

---

## 5. Build the reportlab Lambda layer

reportlab is not in the standard Lambda runtime, so we package it as a layer.

```powershell
mkdir layer\python
pip install reportlab -t layer\python
Compress-Archive -Path layer\python -DestinationPath reportlab-layer.zip -Force

$LAYER_ARN = (aws lambda publish-layer-version `
  --layer-name oms-reportlab `
  --zip-file fileb://reportlab-layer.zip `
  --compatible-runtimes python3.12 `
  --query LayerVersionArn --output text)
```

---

## 6. Deploy all Lambdas

Helper — package a single-file Lambda and create it:

```powershell
function Deploy-Lambda($name, $dir, $envVars, $useLayer = $false) {
  $zip = "$dir\function.zip"
  Compress-Archive -Path "$dir\lambda_function.py" -DestinationPath $zip -Force
  $cmd = @(
    "aws", "lambda", "create-function",
    "--function-name", $name,
    "--runtime", "python3.12",
    "--role", $ROLE_ARN,
    "--handler", "lambda_function.lambda_handler",
    "--zip-file", "fileb://$zip",
    "--timeout", "30",
    "--environment", "Variables={$envVars}"
  )
  if ($useLayer) { $cmd += @("--layers", $LAYER_ARN) }
  & $cmd[0] $cmd[1..($cmd.Length-1)]
}

# Paths — adjust if your folder layout is different
$BASE = "..\lambdas"

Deploy-Lambda "oms-create-order"   "$BASE\create_order"   "TABLE_NAME=$TABLE"
Deploy-Lambda "oms-get-all-orders" "$BASE\get_all_orders" "TABLE_NAME=$TABLE,GSI_NAME=creation_date-index"
Deploy-Lambda "oms-get-order"      "$BASE\get_order"      "TABLE_NAME=$TABLE"
Deploy-Lambda "oms-update-order"   "$BASE\update_order"   "TABLE_NAME=$TABLE"
Deploy-Lambda "oms-delete-order"   "$BASE\delete_order"   "TABLE_NAME=$TABLE"
Deploy-Lambda "oms-stream-handler" "$BASE\stream_handler" "BACKUP_BUCKET=$BUCKET,SNS_TOPIC_ARN=$TOPIC_ARN"
Deploy-Lambda "oms-subscribe"      "$BASE\subscribe"      "SNS_TOPIC_ARN=$TOPIC_ARN"
Deploy-Lambda "oms-unsubscribe"    "$BASE\unsubscribe"    "SNS_TOPIC_ARN=$TOPIC_ARN"
Deploy-Lambda "oms-generate-pdf"   "$BASE\generate_pdf"   "BACKUP_BUCKET=$BUCKET" $true
Deploy-Lambda "oms-scheduled-pdf"  "$BASE\scheduled_pdf"  "BACKUP_BUCKET=$BUCKET" $true
Deploy-Lambda "oms-list-reports"   "$BASE\list_reports"   "BACKUP_BUCKET=$BUCKET"
```

---

## 7. Wire the DynamoDB stream → stream_handler Lambda

```powershell
aws lambda create-event-source-mapping `
  --function-name oms-stream-handler `
  --event-source-arn $STREAM_ARN `
  --starting-position LATEST `
  --batch-size 5
```

---

## 8. Create the API Gateway (REST)

```powershell
$API_ID = (aws apigateway create-rest-api --name $API_NAME --query id --output text)
$ROOT_ID = (aws apigateway get-resources --rest-api-id $API_ID --query "items[0].id" --output text)

function New-Resource($parent, $part) {
  return (aws apigateway create-resource --rest-api-id $API_ID --parent-id $parent --path-part $part --query id --output text)
}

# Resources
$ORDERS    = New-Resource $ROOT_ID "orders"
$ORDER_ID  = New-Resource $ORDERS  "{id}"
$SUBS      = New-Resource $ROOT_ID "subscriptions"
$REPORTS   = New-Resource $ROOT_ID "reports"
$RPT_PDF   = New-Resource $REPORTS "deleted-pdf"
$RPT_SCHED = New-Resource $REPORTS "scheduled"
```

Each route needs: method + integration + Lambda permission + (CORS OPTIONS for browser). The helper below does all of it:

```powershell
function Wire-Route($resourceId, $httpMethod, $lambdaName) {
  $uri = "arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${lambdaName}/invocations"

  aws apigateway put-method --rest-api-id $API_ID --resource-id $resourceId `
      --http-method $httpMethod --authorization-type NONE

  aws apigateway put-integration --rest-api-id $API_ID --resource-id $resourceId `
      --http-method $httpMethod --type AWS_PROXY --integration-http-method POST `
      --uri $uri

  aws lambda add-permission --function-name $lambdaName `
      --statement-id "apigw-$resourceId-$httpMethod" `
      --action lambda:InvokeFunction --principal apigateway.amazonaws.com `
      --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/$httpMethod/*"
}

function Add-Cors($resourceId) {
  aws apigateway put-method --rest-api-id $API_ID --resource-id $resourceId `
      --http-method OPTIONS --authorization-type NONE
  aws apigateway put-integration --rest-api-id $API_ID --resource-id $resourceId `
      --http-method OPTIONS --type MOCK `
      --request-templates '{\"application/json\":\"{\\\"statusCode\\\":200}\"}'
  aws apigateway put-method-response --rest-api-id $API_ID --resource-id $resourceId `
      --http-method OPTIONS --status-code 200 `
      --response-parameters '{\"method.response.header.Access-Control-Allow-Headers\":true,\"method.response.header.Access-Control-Allow-Methods\":true,\"method.response.header.Access-Control-Allow-Origin\":true}'
  aws apigateway put-integration-response --rest-api-id $API_ID --resource-id $resourceId `
      --http-method OPTIONS --status-code 200 `
      --response-parameters '{\"method.response.header.Access-Control-Allow-Headers\":\"''Content-Type''\",\"method.response.header.Access-Control-Allow-Methods\":\"''OPTIONS,GET,POST,PUT,DELETE''\",\"method.response.header.Access-Control-Allow-Origin\":\"''*''\"}'
}

# Wire all routes
Wire-Route $ORDERS    "POST"   "oms-create-order"
Wire-Route $ORDERS    "GET"    "oms-get-all-orders"
Wire-Route $ORDER_ID  "GET"    "oms-get-order"
Wire-Route $ORDER_ID  "PUT"    "oms-update-order"
Wire-Route $ORDER_ID  "DELETE" "oms-delete-order"
Wire-Route $SUBS      "POST"   "oms-subscribe"
Wire-Route $SUBS      "DELETE" "oms-unsubscribe"
Wire-Route $RPT_PDF   "GET"    "oms-generate-pdf"
Wire-Route $RPT_SCHED "GET"    "oms-list-reports"

# CORS for every resource
Add-Cors $ORDERS; Add-Cors $ORDER_ID; Add-Cors $SUBS; Add-Cors $RPT_PDF; Add-Cors $RPT_SCHED

# Deploy
aws apigateway create-deployment --rest-api-id $API_ID --stage-name prod

# Final URL
"https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"
```

Paste that URL into the web client's "API Base URL" field.

---

## 9. EventBridge Scheduler

Allow EventBridge to invoke the scheduled-pdf Lambda:

```powershell
aws lambda add-permission `
  --function-name oms-scheduled-pdf `
  --statement-id "eventbridge-invoke" `
  --action lambda:InvokeFunction `
  --principal events.amazonaws.com

# Create the schedule (every 5 minutes for the demo)
aws events put-rule `
  --name oms-scheduled-pdf-rule `
  --schedule-expression "rate(5 minutes)" `
  --state ENABLED

aws events put-targets `
  --rule oms-scheduled-pdf-rule `
  --targets "Id=1,Arn=arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:oms-scheduled-pdf"

aws lambda add-permission `
  --function-name oms-scheduled-pdf `
  --statement-id "eventbridge-rule-invoke" `
  --action lambda:InvokeFunction `
  --principal events.amazonaws.com `
  --source-arn "arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/oms-scheduled-pdf-rule"
```

After ~10 minutes you should see PDFs under `s3://$BUCKET/reports/scheduled/`, listed in the "Scheduled Reports" tab.

---

## 10. Host the client on AWS Amplify

1. Zip the `client/` folder:
   ```powershell
   Compress-Archive -Path ..\client\* -DestinationPath client.zip -Force
   ```
2. Open the AWS Amplify console → **Host a web app** → **Deploy without Git provider** → drag-drop `client.zip` → Save & Deploy.
3. Amplify returns a public URL like `https://main.dXXXXXX.amplifyapp.com`.
4. Open it, paste the API Gateway URL into the input field, click Save.

---

## 11. Verification CLI commands (one-liners for the report)

| Service | Verification command |
|---|---|
| DynamoDB table | `aws dynamodb describe-table --table-name orders` |
| DynamoDB stream | `aws dynamodb describe-table --table-name orders --query "Table.LatestStreamArn"` |
| S3 bucket | `aws s3api list-objects-v2 --bucket oms-backups-<ACCOUNT_ID>` |
| SNS topic | `aws sns list-subscriptions-by-topic --topic-arn <TOPIC_ARN>` |
| Lambda fn | `aws lambda get-function --function-name oms-delete-order` |
| API Gateway | `aws apigateway get-rest-apis` |
| EventBridge rule | `aws events describe-rule --name oms-scheduled-pdf-rule` |
| Stream → Lambda | `aws lambda list-event-source-mappings --function-name oms-stream-handler` |
| IAM role | `aws iam get-role --role-name oms-lambda-role` |

---

## 12. Tear-down (after grading)

```powershell
aws events remove-targets --rule oms-scheduled-pdf-rule --ids 1
aws events delete-rule --name oms-scheduled-pdf-rule
aws apigateway delete-rest-api --rest-api-id $API_ID
aws lambda list-functions --query "Functions[?starts_with(FunctionName,'oms-')].FunctionName" --output text | ForEach-Object { $_ -split "\s+" } | ForEach-Object { aws lambda delete-function --function-name $_ }
aws dynamodb delete-table --table-name $TABLE
aws s3 rb s3://$BUCKET --force
aws sns delete-topic --topic-arn $TOPIC_ARN
aws iam list-attached-role-policies --role-name $ROLE_NAME --query "AttachedPolicies[].PolicyArn" --output text | ForEach-Object { $_ -split "\s+" } | ForEach-Object { aws iam detach-role-policy --role-name $ROLE_NAME --policy-arn $_ }
aws iam delete-role --role-name $ROLE_NAME
```
