"""Upload all COCO images to S3.

Reads COCO annotations to get every unique image URL, downloads each
image from the COCO servers, and uploads to S3 under photos/{image_id}.jpg.

Supports resuming: skips photos that already exist in S3.

Usage:
    python upload_photos_to_s3.py                          # default bucket from .env
    python upload_photos_to_s3.py --bucket my-bucket-name  # explicit bucket
    python upload_photos_to_s3.py --max-workers 20         # control concurrency
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ANNOTATIONS_URL = (
    "http://images.cocodataset.org/annotations/annotations_trainval2017.zip"
)
ROOT_DIR = Path(__file__).resolve().parent.parent
ANNOTATIONS_DIR = ROOT_DIR / "annotations"


def download_annotations() -> tuple[Path, Path]:
    """Download and extract COCO annotations. Returns paths to train and val files."""
    zip_path = ANNOTATIONS_DIR / "annotations_trainval2017.zip"
    train_file = ANNOTATIONS_DIR / "annotations" / "captions_train2017.json"
    val_file = ANNOTATIONS_DIR / "annotations" / "captions_val2017.json"

    if not zip_path.exists():
        ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {ANNOTATIONS_URL}...")
        urllib.request.urlretrieve(ANNOTATIONS_URL, str(zip_path))
        print("Download complete.")

    if not train_file.exists() or not val_file.exists():
        print("Extracting annotations...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(ANNOTATIONS_DIR)

    return train_file, val_file


def extract_image_urls(caption_files: list[Path]) -> dict[str, str]:
    """Extract all unique {image_id: coco_url} pairs from caption files."""
    images: dict[str, str] = {}
    for file_path in caption_files:
        print(f"Parsing {file_path.name}...")
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for img in data["images"]:
            images[str(img["id"])] = img["coco_url"]
    return images


def s3_key_exists(s3_client, bucket: str, key: str) -> bool:
    """Check if an S3 key exists."""
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def upload_single_photo(
    s3_client, bucket: str, image_id: str, url: str
) -> tuple[str, bool, str]:
    """Download one photo from COCO and upload to S3.

    Returns (image_id, success, message).
    """
    key = f"photos/{image_id}.jpg"

    if s3_key_exists(s3_client, bucket, key):
        return image_id, True, "skipped (exists)"

    try:
        resp = urllib.request.urlopen(url, timeout=30)
        data = resp.read()
        s3_client.put_object(Bucket=bucket, Key=key, Body=data, ContentType="image/jpeg")
        return image_id, True, "uploaded"
    except Exception as exc:
        return image_id, False, str(exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload COCO images to S3")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET", ""), help="S3 bucket name")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"), help="AWS region")
    parser.add_argument("--max-workers", type=int, default=10, help="Concurrent upload threads")
    args = parser.parse_args()

    if not args.bucket:
        print("Error: S3_BUCKET not set. Use --bucket or set S3_BUCKET in .env")
        return

    print(f"Target bucket: {args.bucket}")
    print(f"Region: {args.region}")
    print(f"Concurrency: {args.max_workers}")

    train_file, val_file = download_annotations()
    images = extract_image_urls([train_file, val_file])
    print(f"Total unique images: {len(images)}")

    s3_client = boto3.client("s3", region_name=args.region)

    uploaded = 0
    skipped = 0
    failed = 0
    total = len(images)

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(upload_single_photo, s3_client, args.bucket, img_id, url): img_id
            for img_id, url in images.items()
        }

        for i, future in enumerate(as_completed(futures), 1):
            img_id, success, message = future.result()
            if success:
                if "skipped" in message:
                    skipped += 1
                else:
                    uploaded += 1
            else:
                failed += 1
                print(f"  FAILED {img_id}: {message}")

            if i % 500 == 0 or i == total:
                print(f"Progress: {i}/{total} (uploaded={uploaded}, skipped={skipped}, failed={failed})")

    print(f"\nDone! uploaded={uploaded}, skipped={skipped}, failed={failed}")


if __name__ == "__main__":
    main()
