"""Upload a large creator-media file in bounded multipart chunks."""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
from pathlib import Path
from typing import Any

from infrai_storage import InfraiClient


PART_SIZE = 8 * 1024 * 1024


def _operation_key(bucket: str, key: str, source: Path) -> str:
    stat = source.stat()
    value = f"{bucket}\0{key}\0{stat.st_size}\0{stat.st_mtime_ns}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def upload_media(source: Path, bucket: str, key: str, client: InfraiClient) -> dict[str, Any]:
    operation = _operation_key(bucket, key, source)
    client.create_bucket(bucket, f"bucket:{bucket}")
    content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    created = client.create_multipart(bucket, key, content_type, f"upload:{operation}")
    upload_id = str(created["upload_id"])
    parts: list[dict[str, object]] = []

    try:
        with source.open("rb") as stream:
            part_number = 1
            while chunk := stream.read(PART_SIZE):
                signed = client.presign_part(upload_id, part_number)
                etag = client.put_part(str(signed["url"]), chunk)
                parts.append({"part_number": part_number, "etag": etag})
                part_number += 1

        if not parts:
            raise ValueError("The media file is empty")
        return client.complete_multipart(upload_id, parts, f"complete:{operation}")
    except Exception:
        client.abort_multipart(upload_id)
        client.delete_bucket(bucket)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a large media file by multipart upload")
    parser.add_argument("source", type=Path)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--key", required=True)
    args = parser.parse_args()
    result = upload_media(args.source, args.bucket, args.key, InfraiClient())
    print(result)


if __name__ == "__main__":
    main()
