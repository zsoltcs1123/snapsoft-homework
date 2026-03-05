import io
import logging
import os
from urllib.parse import unquote_plus

import boto3
import pandas as pd

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

CURATED_BUCKET = os.environ.get("CURATED_BUCKET")
if not CURATED_BUCKET:
    raise RuntimeError("CURATED_BUCKET environment variable is not set")

COLUMNS_TO_DROP = [
    "car_ID",
    "CarName",
    "ownername",
    "owneremail",
    "dealershipaddress",
    "saledate",
    "iban",
]

CRITICAL_COLUMNS = ["carbody", "fueltype", "drivewheel", "Price"]


def lambda_handler(event, context):
    try:
        source_bucket, object_key = parse_s3_event(event)

        if not object_key.lower().endswith(".csv"):
            logger.warning("Skipping non-CSV object: %s", object_key)
            return skipped_response(object_key, reason="not a CSV file")

        raw_df = read_csv_from_s3(source_bucket, object_key)
        cleaned_df = preprocess(raw_df)
        write_csv_to_s3(cleaned_df, CURATED_BUCKET, object_key)

        logger.info(
            "Processed %s: %d rows -> %d rows",
            object_key,
            len(raw_df),
            len(cleaned_df),
        )
        return success_response(
            object_key, raw_rows=len(raw_df), cleaned_rows=len(cleaned_df)
        )
    except Exception:
        logger.exception("Failed to process event")
        raise


def parse_s3_event(event):
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = unquote_plus(record["s3"]["object"]["key"])
    return bucket, key


def read_csv_from_s3(bucket, key):
    response = s3.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read()
    return pd.read_csv(io.BytesIO(body))


def preprocess(df):
    df = drop_non_ml_columns(df)
    df = drop_incomplete_rows(df)
    return df


def drop_non_ml_columns(df):
    return df.drop(columns=COLUMNS_TO_DROP, errors="ignore")


def drop_incomplete_rows(df):
    present_critical = [c for c in CRITICAL_COLUMNS if c in df.columns]
    before = len(df)
    df = df.dropna(subset=present_critical)
    dropped = before - len(df)
    if dropped:
        logger.info("Dropped %d rows missing critical columns", dropped)
    return df


def write_csv_to_s3(df, bucket, key):
    csv_buffer = df.to_csv(index=False)
    s3.put_object(Bucket=bucket, Key=key, Body=csv_buffer.encode("utf-8"))


def success_response(object_key, *, raw_rows, cleaned_rows):
    return {
        "status": "success",
        "object_key": object_key,
        "raw_rows": raw_rows,
        "cleaned_rows": cleaned_rows,
        "rows_dropped": raw_rows - cleaned_rows,
    }


def skipped_response(object_key, *, reason):
    return {
        "status": "skipped",
        "object_key": object_key,
        "reason": reason,
    }
