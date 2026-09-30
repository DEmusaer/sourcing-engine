#!/usr/bin/env python3
"""
Backup rate_library.csv to AWS S3.
Run on a schedule (e.g., daily via cron or Kubernetes CronJob).
Requires AWS credentials via environment variables or IAM role.
"""

import os
import sys
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

# Configuration from environment
DATA_DIR = os.environ.get("DATA_DIR", ".")
RATE_LIBRARY_PATH = os.path.join(DATA_DIR, "rate_library.csv")
S3_BUCKET = os.environ.get("S3_BUCKET")
S3_PREFIX = os.environ.get("S3_PREFIX", "sourcing-engine-backups")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def backup_to_s3():
    """Upload rate_library.csv to S3 with timestamp."""
    if not S3_BUCKET:
        print("ERROR: S3_BUCKET environment variable not set. Skipping backup.")
        return False

    if not os.path.exists(RATE_LIBRARY_PATH):
        print(f"WARNING: {RATE_LIBRARY_PATH} not found. Skipping backup.")
        return False

    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)

        # Generate timestamped key
        timestamp = datetime.utcnow().isoformat() + "Z"
        s3_key = f"{S3_PREFIX}/{timestamp}/rate_library.csv"

        # Upload file
        s3.upload_file(RATE_LIBRARY_PATH, S3_BUCKET, s3_key)
        print(f"✓ Backed up to s3://{S3_BUCKET}/{s3_key}")

        # Also upload as 'latest' for easy recovery
        latest_key = f"{S3_PREFIX}/latest/rate_library.csv"
        s3.upload_file(RATE_LIBRARY_PATH, S3_BUCKET, latest_key)
        print(f"✓ Updated s3://{S3_BUCKET}/{latest_key}")

        return True

    except ClientError as e:
        print(f"ERROR: S3 upload failed: {e}")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        return False


def restore_from_s3():
    """Download rate_library.csv from S3 (latest version)."""
    if not S3_BUCKET:
        print("ERROR: S3_BUCKET environment variable not set. Cannot restore.")
        return False

    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        latest_key = f"{S3_PREFIX}/latest/rate_library.csv"

        s3.download_file(S3_BUCKET, latest_key, RATE_LIBRARY_PATH)
        print(f"✓ Restored from s3://{S3_BUCKET}/{latest_key}")
        print(f"  Saved to {RATE_LIBRARY_PATH}")

        return True

    except ClientError as e:
        print(f"ERROR: S3 download failed: {e}")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        return False


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "backup"

    if action == "backup":
        success = backup_to_s3()
        sys.exit(0 if success else 1)
    elif action == "restore":
        success = restore_from_s3()
        sys.exit(0 if success else 1)
    else:
        print(f"Usage: backup.py [backup|restore]")
        sys.exit(1)
