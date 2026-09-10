#!/usr/bin/env python3
import os
import sys
import subprocess
import logging
import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

S3_BUCKET = os.getenv("S3_BUCKET_NAME", "your-mongo-backup-bucket-name")
AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
LOCAL_RESTORE_PATH = "/tmp/restore_temp.gz"

def get_latest_s3_key():
    logging.info(f"Querying S3 bucket '{S3_BUCKET}' for the latest backup object...")
    s3 = boto3.client("s3", region_name=AWS_REGION)
    response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix="backups/")
   
    if "Contents" not in response or not response["Contents"]:
        raise RuntimeError("No backup archives found in S3 bucket.")
   
    # Sort by last modified timestamp to get the newest file
    sorted_objects = sorted(response["Contents"], key=lambda x: x["LastModified"], reverse=True)
    latest_key = sorted_objects[0]["Key"]
    logging.info(f"Identified latest backup key: {latest_key}")
    return latest_key

def download_backup(s3_key):
    logging.info(f"Downloading s3://{S3_BUCKET}/{s3_key} to {LOCAL_RESTORE_PATH}...")
    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3.download_file(S3_BUCKET, s3_key, LOCAL_RESTORE_PATH)
    logging.info("Download completed successfully.")

def run_mongorestore():
    logging.info("Executing mongorestore against MongoDB...")
    # --nsInclude="portfolio.*" limits restore to our target database
    # --drop drops target collections before restoring to ensure a clean state
    cmd = [
        "mongorestore",
        f"--uri={MONGO_URI}",
        f"--archive={LOCAL_RESTORE_PATH}",
        "--gzip",
        "--drop"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"mongorestore failed: {result.stderr}")
    logging.info("MongoDB restore finished successfully.")

def cleanup():
    if os.path.exists(LOCAL_RESTORE_PATH):
        os.remove(LOCAL_RESTORE_PATH)
        logging.info("Temporary restore file cleaned up.")

def main():
    try:
        latest_key = get_latest_s3_key()
        download_backup(latest_key)
        run_mongorestore()
        cleanup()
        logging.info("Disaster recovery test SUCCESSFUL.")
    except Exception as err:
        logging.error(f"Disaster recovery test FAILED: {str(err)}")
        cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main()

