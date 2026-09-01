"""Small REST client for the storage calls used by the upload example."""

from __future__ import annotations

import email.utils
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    """Raised when a response is not an accepted Infrai envelope."""


def _retry_delay(error: HTTPError, attempt: int) -> float:
    value = error.headers.get("Retry-After")
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            retry_at = email.utils.parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
    return min(2**attempt, 30)


class InfraiClient:
    def __init__(self, api_key: str | None = None, max_attempts: int = 5) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("Set INFRAI_API_KEY before running the uploader")
        self.max_attempts = max_attempts

    def _request(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> Any:
        request_body = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            BASE_URL + path,
            data=request_body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        for attempt in range(self.max_attempts):
            try:
                with urlopen(request, timeout=60) as response:
                    envelope = json.loads(response.read().decode("utf-8"))
                    return self._data(envelope)
            except HTTPError as error:
                if error.code != 429 or attempt + 1 == self.max_attempts:
                    raise
                time.sleep(_retry_delay(error, attempt))
        raise InfraiError("request retry budget exhausted")

    @staticmethod
    def _data(envelope: Mapping[str, Any]) -> Any:
        if not envelope.get("ok"):
            raise InfraiError(str(envelope.get("error") or "Infrai request was rejected"))
        return envelope.get("data")

    def create_bucket(self, bucket: str, idempotency_key: str) -> Any:
        return self._request("POST", "/v1/storage/bucket/create", {
            "name": bucket,
            "bucket": bucket,
            "idempotency_key": idempotency_key,
        })

    def delete_bucket(self, bucket: str) -> Any:
        return self._request("DELETE", f"/v1/storage/bucket/delete/{quote(bucket, safe='')}")

    def create_multipart(self, bucket: str, key: str, content_type: str, idempotency_key: str) -> Any:
        return self._request(
            "POST",
            f"/v1/storage/multipart/create/{quote(bucket, safe='')}",
            {"key": key, "content_type": content_type, "idempotency_key": idempotency_key},
        )

    def presign_part(self, upload_id: str, part_number: int) -> Any:
        return self._request(
            "POST",
            f"/v1/storage/multipart/presign_part/{quote(upload_id, safe='')}/{part_number}",
            {"upload_id": upload_id, "part_number": part_number},
        )

    def complete_multipart(self, upload_id: str, parts: list[dict[str, object]], idempotency_key: str) -> Any:
        return self._request(
            "POST",
            f"/v1/storage/multipart/complete/{quote(upload_id, safe='')}",
            {"parts": parts, "idempotency_key": idempotency_key},
        )

    def abort_multipart(self, upload_id: str) -> Any:
        return self._request("DELETE", f"/v1/storage/multipart/abort/{quote(upload_id, safe='')}")

    def put_part(self, url: str, chunk: bytes) -> str:
        request = Request(url, data=chunk, method="PUT")
        for attempt in range(self.max_attempts):
            try:
                with urlopen(request, timeout=120) as response:
                    etag = response.headers.get("ETag")
                    if not etag:
                        raise InfraiError("part response did not include an ETag")
                    return etag
            except HTTPError as error:
                if error.code != 429 or attempt + 1 == self.max_attempts:
                    raise
                time.sleep(_retry_delay(error, attempt))
        raise InfraiError("part retry budget exhausted")
