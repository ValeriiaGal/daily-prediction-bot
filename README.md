# Daily Prediction Telegram Bot

Serverless Telegram bot that sends a random prediction with a random photo every morning. Runs on AWS Lambda, no server needed.

**Stack:** Python, AWS Lambda, Amazon S3, EventBridge Scheduler, IAM, CloudWatch, Telegram Bot API

## How it works
1. EventBridge Scheduler triggers the Lambda once a day (Europe/Warsaw time)
2. The Lambda picks a random line from `predictions.txt` and a random photo from `photos/` in S3
3. It sends them to the chat through the Telegram Bot API


