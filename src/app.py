import json
import mimetypes
import os
import random
import urllib.error
import urllib.request
import uuid

import boto3

PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

s3 = boto3.client("s3")


def pick_prediction(bucket):
    body = s3.get_object(Bucket=bucket, Key="predictions.txt")["Body"].read()
    lines = [line.strip() for line in body.decode("utf-8").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("predictions.txt is empty")
    return random.choice(lines)


def pick_photo(bucket):
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="photos/"):
        for obj in page.get("Contents", []):
            if obj["Key"].lower().endswith(PHOTO_EXTENSIONS):
                keys.append(obj["Key"])

    if not keys:
        raise RuntimeError(f"no photos found in s3://{bucket}/photos/")

    key = random.choice(keys)
    data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    return key, data


def build_multipart(fields, filename, file_bytes):
    boundary = uuid.uuid4().hex
    parts = []

    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode("utf-8")
        )

    content_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="photo"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
    )
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def send_photo(token, chat_id, caption, filename, file_bytes):
    body, content_type = build_multipart(
        {"chat_id": chat_id, "caption": caption}, filename, file_bytes
    )

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        data=body,
        headers={"Content-Type": content_type},
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Telegram API error {error.code}: {error.read().decode()}") from error


def lambda_handler(event, context):
    token = os.environ["BOT_TOKEN"]
    chat_id = os.environ["CHAT_ID"]
    bucket = os.environ["ASSETS_BUCKET"]

    prediction = pick_prediction(bucket)
    key, photo_bytes = pick_photo(bucket)

    print(f"photo: {key} ({len(photo_bytes)} bytes)")

    result = send_photo(token, chat_id, prediction, os.path.basename(key), photo_bytes)

    print(f"sent: {prediction}")
    return {"ok": result.get("ok", False), "prediction": prediction, "photo": key}