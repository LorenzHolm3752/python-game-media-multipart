import io
import tempfile
import unittest
from pathlib import Path

from upload_media import upload_media


class RecordingClient:
    def __init__(self):
        self.calls = []

    def create_bucket(self, bucket, idempotency_key):
        self.calls.append(("bucket", bucket, idempotency_key))

    def create_multipart(self, bucket, key, content_type, idempotency_key):
        self.calls.append(("create", bucket, key, content_type, idempotency_key))
        return {"upload_id": "media-upload-1"}

    def presign_part(self, upload_id, part_number):
        self.calls.append(("sign", upload_id, part_number))
        return {"url": f"part-{part_number}"}

    def put_part(self, url, chunk):
        self.calls.append(("put", url, chunk))
        return f"etag-{url}"

    def complete_multipart(self, upload_id, parts, idempotency_key):
        self.calls.append(("complete", upload_id, parts, idempotency_key))
        return {"key": "clips/demo.mp4", "size_bytes": 6}

    def abort_multipart(self, upload_id):
        self.calls.append(("abort", upload_id))

    def delete_bucket(self, bucket):
        self.calls.append(("delete-bucket", bucket))


class UploadMediaTest(unittest.TestCase):
    def test_keeps_parts_in_order_and_creates_bucket_first(self):
        client = RecordingClient()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "demo.mp4"
            source.write_bytes(b"abcdef")
            import upload_media as module
            old_size = module.PART_SIZE
            module.PART_SIZE = 3
            try:
                result = upload_media(source, "creator-media", "clips/demo.mp4", client)
            finally:
                module.PART_SIZE = old_size
        self.assertEqual(result["size_bytes"], 6)
        self.assertEqual(client.calls[0][0], "bucket")
        self.assertEqual(client.calls[-1][2], [
            {"part_number": 1, "etag": "etag-part-1"},
            {"part_number": 2, "etag": "etag-part-2"},
        ])

    def test_cleans_up_when_a_part_fails(self):
        client = RecordingClient()
        client.put_part = lambda url, chunk: (_ for _ in ()).throw(RuntimeError("upload failed"))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "demo.mp4"
            source.write_bytes(b"abcdef")
            with self.assertRaisesRegex(RuntimeError, "upload failed"):
                upload_media(source, "creator-media", "clips/demo.mp4", client)
        self.assertEqual(client.calls[-2:], [("abort", "media-upload-1"), ("delete-bucket", "creator-media")])


if __name__ == "__main__":
    unittest.main()
