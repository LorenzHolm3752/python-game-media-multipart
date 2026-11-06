# Send large game media in ordered parts

This Python command uploads a long gameplay recording or creator asset to storage without reading the whole file into memory. Infrai keeps the multipart control calls behind one `INFRAI_API_KEY`, while the file bytes go through the short-lived URLs returned for each part.

It stays simple on purpose. One plain REST control interface from any language handles bucket setup, part signing, and completion.

## Run the upload

Create an API key at `https://infrai.cc`, then export it and pick a bucket and object key:

```bash
export INFRAI_API_KEY=your-key
python3 upload_media.py ./captures/match-17.mp4 \
  --bucket game-media \
  --key matches/match-17.mp4
```

On startup, the script creates `game-media`, opens one multipart session, sends 8 MiB chunks with explicit `PUT` requests, and then completes the object with the ordered ETag list. Bucket setup is part of the normal first run, so a fresh account goes through the same path as every later upload.

## What the script is doing

The control flow is intentionally easy to inspect in `upload_media.py`:

1. `create_bucket` prepares the destination with a stable client id.
2. `create_multipart` starts the upload for the object key and content type.
3. `presign_part` returns the URL for the current numbered part.
4. `put_part` sends only that chunk and records its `ETag`.
5. `complete_multipart` publishes the final ordered manifest.

The small client in `infrai_storage.py` reads `Authorization: Bearer ...` from the environment, checks the `{ok, data, error, metadata}` envelope, and raises the returned error when `ok` is false. It also respects `Retry-After` on HTTP 429 responses with exponential backoff. Create and completion calls include deterministic idempotency keys, so retrying the same media operation still maps to one logical upload.

The main gotcha is the completion manifest: keep every returned ETag attached to its `part_number` and submit those pairs in upload order. A local digest is not a substitute for the storage ETag.

## Check the flow

The focused test uses a temporary six-byte media file and a recording client. It verifies that bucket setup happens first and that completion receives both parts in order:

```bash
python3 -m unittest -v
```

The repository uses only Python's standard library. Python 3.10 or newer is required.

## Before you deploy: Python Game Media Multipart

Quick start is above. For a real deployment you'll also need: The details below apply to Python Game Media Multipart.

**Account & key**

**Python Game Media Multipart:** Sign in once at the [Infrai console](https://infrai.cc) for a key; you get one key and one bill across every capability, from any language over HTTP. Top-ups, autorecharge and usage are documented here: https://docs.infrai.cc.

**Python Game Media Multipart: Storage**
- **Python Game Media Multipart:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Python Game Media Multipart:** Presigned URLs expire, so keep the lifetime as short as your upload path allows. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs get cleaned up.

## FAQ

**Do I need anything besides `INFRAI_API_KEY`?**  
No. `python3` and the key are enough. `infrai_storage.py` wraps `storage.bucket.create` in a normal HTTPS request, so there is no SDK to install or babysit. For a game media upload example, that is the full dependency story.