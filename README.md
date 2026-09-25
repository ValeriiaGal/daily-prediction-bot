# Daily Prediction Bot

## Overview

A Telegram bot that delivers one short prediction for the day, paired with a
random photo, every morning at 10:00. Predictions are plain sentences. Things
like *"Today rewards whoever starts before they feel ready"* or *"Save your
work. Twice."* Each one is drawn at random from a list of 100 and sent as the
caption on a randomly chosen photo.

The bot is fully serverless. The function wakes up once a day, sends a message,
and stops.

## Project structure

```
daily-prediction-bot/
├── src/
│   └── app.py              # the Lambda
├── assets/
│   ├── predictions.txt     # 100 predictions, one per line
│   └── photos/             # images, uploaded to S3
├── requirements.txt
├── .env.example            # the variables the function expects
└── README.md
```

The contents of `assets/` are uploaded to S3; the repository keeps the
canonical copy so the bot's content is versioned alongside its code. Blank
lines in `predictions.txt` are ignored, and the bot accepts JPEG, PNG and WebP
images.

## Architecture

| Component | Role |
|---|---|
| AWS Lambda | Runs the bot logic: picks a prediction, picks a photo, sends the message. |
| Amazon S3 | Stores `predictions.txt` and the photo library. |
| Amazon EventBridge Scheduler | Invokes the Lambda function once a day at 10:00 Europe/Warsaw. |
| AWS IAM | Grants the function read access to one specific bucket and nothing else. |
| Amazon CloudWatch | Collects execution logs and metrics automatically. |
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
to Telegram as `multipart/form-data`, so the bucket needs no public access and
no signed links.

## Deployment Steps

### 1. Create the Telegram bot

1. In Telegram, start a chat with **@BotFather** and send `/newbot`. Choose a
   display name and a username ending in `bot`, and save the token.
2. Press **Start** in your new bot's chat, then send it any message.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and find
   `"chat":{"id":123456789}` — that number is your chat ID.

### 2. Create the S3 bucket

1. **S3** → **Create bucket**. Pick a globally unique name and leave
   **Block all public access** enabled.
2. Upload `predictions.txt` to the root, and the images into a `photos/`
   folder.

Object keys should use plain names without spaces.

### 3. Create the Lambda function

1. **Lambda** → **Create function** → **Author from scratch**, runtime
   **Python 3.13**.
2. Paste `src/app.py` into `lambda_function.py` and **Deploy**.
3. **Configuration → General configuration**: set the **Timeout** to
   **30 seconds**. The default of 3 seconds is not enough to download an image
   and upload it to Telegram.
4. **Configuration → Environment variables**:

| Key | Value |
|---|---|
| `BOT_TOKEN` | Telegram bot token |
| `CHAT_ID` | Telegram chat ID |
| `ASSETS_BUCKET` | bucket name |

### 4. Grant access to the bucket

**Configuration → Permissions** → click the execution **Role name** →
**Add permissions → Create inline policy → JSON**:

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

Both ARNs are needed: listing the bucket is a permission on the bucket itself,
reading a file is a permission on the objects inside it. A scoped policy is
used instead of `AmazonS3ReadOnlyAccess` so the function can only reach the one
bucket it needs.

### 5. Create the schedule

**EventBridge Scheduler** → **Create schedule** → recurring, cron-based:

- Cron expression: `cron(0 10 * * ? *)`
- Timezone: `Europe/Warsaw`
- Flexible time window: **Off**
- Target: AWS Lambda → your function

### 6. Monitor

The Lambda **Monitor** tab shows invocation counts, duration and errors.
**View CloudWatch logs** shows individual runs — each one logs which photo it
picked and which prediction it sent.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in your three values
```

`.env` holds the same three variables Lambda receives as environment variables.
It is gitignored and must never be committed — a leaked bot token gives anyone
control of the bot.

## Key Features

- **Runs unattended.** Nothing to start, restart or maintain once deployed.
- **No idle cost.** 30 invocations a month sit inside Lambda's permanent free
  tier.
- **Content is data, not code.** Predictions and photos are S3 objects, so the
  output changes by uploading a file rather than redeploying.
- **No runtime dependencies.** Standard library plus `boto3`, which Lambda
  already provides.
- **Correct across daylight saving.** EventBridge Scheduler takes a real
  timezone, so 10:00 stays 10:00 all year with no date logic in the code.
- **Private by default.** Image bytes go straight to Telegram, so the bucket
  needs no public access, bucket policy or presigned URLs.