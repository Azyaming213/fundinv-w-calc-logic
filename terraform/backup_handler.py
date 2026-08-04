import json
import os
import subprocess

import boto3
from datetime import datetime, timezone

secrets = boto3.client("secretsmanager")
s3 = boto3.client("s3")


def handler(event, context):
    secret = json.loads(
        secrets.get_secret_value(
            SecretId=os.environ["DB_SECRET_ARN"]
        )["SecretString"]
    )

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d/%H%M")
    key = f"backups/{ts}/fundinv.sql.gz"
    bucket = os.environ["BACKUPS_BUCKET"]

    env = os.environ.copy()
    env["PGPASSWORD"] = secret["password"]
    env["LD_LIBRARY_PATH"] = "/opt/lib"

    pg_dump = subprocess.Popen(
        [
            "/opt/bin/pg_dump",
            "-h", secret["host"],
            "-p", str(secret["port"]),
            "-U", secret["username"],
            "-d", secret["dbname"],
            "--no-owner",
            "--no-acl",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    gzip = subprocess.Popen(
        ["/opt/bin/gzip"],
        stdin=pg_dump.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    pg_dump.stdout.close()
    compressed, gzip_err = gzip.communicate()
    _, pg_err = pg_dump.communicate()

    if pg_dump.returncode != 0:
        err = pg_err.decode() if pg_err else "unknown error"
        raise RuntimeError(f"pg_dump failed (rc={pg_dump.returncode}): {err}")

    if gzip.returncode != 0:
        err = gzip_err.decode() if gzip_err else "unknown error"
        raise RuntimeError(f"gzip failed (rc={gzip.returncode}): {err}")

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=compressed,
        ContentType="application/gzip",
    )

    print(f"Backup written to s3://{bucket}/{key} ({len(compressed)} bytes)")
