# Daily Prediction Bot

## Overview

A Telegram bot that delivers one short prediction for the day, paired with a
random photo, every morning at 10:00. Predictions are plain sentences — things
like *"Today rewards whoever starts before they feel ready"* or *"Save your
work. Twice."* — drawn at random from a list of 100, and each one is sent with
a randomly chosen image as the caption.

The bot is fully serverless. Nothing runs between deliveries: the function
wakes up once a day, sends a message, and stops. A typical run takes about 1.4
seconds.

## Content

Both the text and the images live in S3 as ordinary files, so the bot's content
can be changed without touching the code.

| File | Contents |
|---|---|
| `predictions.txt` | 100 predictions, one per line. Blank lines are ignored. |
| `photos/` | JPEG and PNG images. Any number; the bot lists them at runtime. |

Adding a new prediction means editing a text file. Adding a new photo means
uploading it. Neither requires a redeploy.

## Architecture

| Component | Role |
|---|---|
| AWS Lambda | Runs the bot logic: picks a prediction, picks a photo, sends the message. |
| Amazon S3 | Stores `predictions.txt` and the photo library. |
| Amazon EventBridge Scheduler | Invokes the Lambda function once a day at 10:00 Europe/Warsaw. |
| AWS IAM | Grants the function read access to one specific bucket and nothing else. |
| Amazon CloudWatch | Collects execution logs and metrics. |
| Telegram Bot API | Receives the photo and caption and delivers them to the chat. |

## Data Flow

```
EventBridge Scheduler
     │
     │ daily trigger — 10:00 Europe/Warsaw
     ▼
   AWS Lambda
     │
     ├──────────────▶ Amazon S3
     │                    │
     │                    │ predictions.txt + one random photo
     │                    ▼
     │
     └──────────────▶ Telegram Bot API
                          │
                          ▼
                    Telegram Chat
```

The function downloads the chosen image from S3 and uploads the bytes directly
to Telegram as `multipart/form-data`. The bucket is never exposed to the
internet and needs no public access or signed links.

Execution logs are written automatically:

```
AWS Lambda
     │
     │ execution logs
     ▼
Amazon CloudWatch
```

## Deployment Steps

The steps below set the project up from scratch in the AWS Console.

### 1. Create the Telegram bot

1. Open Telegram and start a chat with **@BotFather**.
2. Send `/newbot`, choose a display name and a username ending in `bot`. Save
   the token it returns.
3. Press **Start** in your new bot's chat, then send it any message.
4. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser,
   substituting your token.
5. In the JSON, find `"chat":{"id":123456789}` — that number is your chat ID.

Keep the token and the chat ID for step 3.

### 2. Create the S3 bucket

1. In the AWS Console, go to **S3** → **Create bucket**.
2. Choose a globally unique name and leave **Block all public access** enabled.
3. Open the bucket and upload `predictions.txt` to the root.
4. Create a folder called `photos` and upload the images into it.

Object keys should use plain names without spaces.

### 3. Create the Lambda function

1. Go to **Lambda** → **Create function** → **Author from scratch**.
2. Choose a name and select the **Python 3.13** runtime.
3. Paste the contents of `src/app.py` into `lambda_function.py` and click
   **Deploy**.
4. Open **Configuration → General configuration → Edit** and set the
   **Timeout** to **30 seconds**. The default of 3 seconds is not enough to
   download an image and upload it to Telegram.
5. Open **Configuration → Environment variables** and add:

| Key | Value |
|---|---|
| `BOT_TOKEN` | Telegram bot token from step 1 |
| `CHAT_ID` | Telegram chat ID from step 1 |
| `ASSETS_BUCKET` | bucket name from step 2 |

### 4. Grant access to the bucket

1. Open **Configuration → Permissions** and click the execution **Role name**
   to open it in IAM.
2. Choose **Add permissions → Create inline policy → JSON** and paste:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:ListBucket"],
            "Resource": [
                "arn:aws:s3:::YOUR-BUCKET-NAME",
                "arn:aws:s3:::YOUR-BUCKET-NAME/*"
            ]
        }
    ]
}
```

3. Name the policy and create it.

Both ARNs are needed: listing the bucket is a permission on the bucket itself,
while reading a file is a permission on the objects inside it. A scoped policy
like this is used instead of the built-in `AmazonS3ReadOnlyAccess` so the
function can only reach the one bucket it actually needs.

### 5. Create the schedule

1. Search for **EventBridge Scheduler** → **Create schedule**.
2. **Schedule pattern**: Recurring schedule, **Cron-based**.
3. Cron expression: `cron(0 10 * * ? *)`
4. **Timezone**: `Europe/Warsaw`
5. **Flexible time window**: **Off**, so the message arrives on time rather
   than within a 15-minute window.
6. **Target**: AWS Lambda → your function.
7. Allow the wizard to create a new execution role, then create the schedule.

### 6. Monitor

Open the Lambda function's **Monitor** tab for invocation counts, duration and
errors, or **View CloudWatch logs** for the output of individual runs. Each run
logs which photo it picked and which prediction it sent.

## Key Features

- **Runs unattended.** Once deployed there is nothing to start, restart or
  maintain.
- **No idle cost.** Serverless and pay-per-execution; 30 invocations a month
  sit comfortably inside Lambda's permanent free tier.
- **Content is data, not code.** Predictions and photos are S3 objects, so the
  bot's output changes by uploading a file rather than by redeploying.
- **No runtime dependencies.** The function uses only the Python standard
  library plus `boto3`, which Lambda already provides — the deployment artifact
  is a single file with no build step.
- **Correct across daylight saving.** EventBridge Scheduler is given a real
  timezone rather than a UTC offset, so 10:00 stays 10:00 all year without any
  date logic in the code.
- **Private by default.** Image bytes are uploaded to Telegram directly, so the
  bucket needs no public access, no bucket policy and no presigned URLs.