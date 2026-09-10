#!/usr/bin/env python3
import os
import sys
import subprocess
import logging
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Environment & Configuration Defaults
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "your-mongo-backup-bucket-name")
AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://127.0.0.1:27017/?replicaSet=rs0&readPreference=secondaryPreferred"
)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_FILENAME = f"mongo_backup_{TIMESTAMP}.gz"
LOCAL_BACKUP_PATH = f"/tmp/{BACKUP_FILENAME}"
S3_KEY = f"backups/{datetime.now().strftime('%Y/%m/%d')}/{BACKUP_FILENAME}"

def send_alert(subject, message):
    if not SNS_TOPIC_ARN:
        return
    try:
        sns = boto3.client("sns", region_name=AWS_REGION)
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=message)
    except Exception as e:
        logging.error(f"Failed to dispatch SNS alert: {e}")

def run_mongodump():
    logging.info("Executing mongodump archive against secondary...")
    cmd = [
        "mongodump",
        f"--uri={MONGO_URI}",
        f"--archive={LOCAL_BACKUP_PATH}",
        "--gzip"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"mongodump execution failed: {result.stderr}")
    logging.info(f"Archive generated at {LOCAL_BACKUP_PATH}")

def upload_backup():
    logging.info(f"Uploading {LOCAL_BACKUP_PATH} to s3://{S3_BUCKET}/{S3_KEY}...")
    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3.upload_file(LOCAL_BACKUP_PATH, S3_BUCKET, S3_KEY)
    logging.info("S3 upload completed successfully.")

def cleanup_local():
    if os.path.exists(LOCAL_BACKUP_PATH):
        os.remove(LOCAL_BACKUP_PATH)
        logging.info("Local temporary archive cleaned up.")

def main():
    try:
        run_mongodump()
        upload_backup()
        cleanup_local()
        send_alert("SUCCESS: MongoDB S3 Backup", f"Archive uploaded successfully: s3://{S3_BUCKET}/{S3_KEY}")
    except Exception as err:
        error_details = f"Backup failed: {str(err)}"
        logging.error(error_details)
        cleanup_local()
        send_alert("CRITICAL: MongoDB S3 Backup Failure", error_details)
        sys.exit(1)

if __name__ == "__main__":
    main()
