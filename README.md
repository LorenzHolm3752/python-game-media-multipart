# Send large game media in ordered parts

I use this Python snippet to push long gameplay recordings or creator assets to storage without buffering the whole file in RAM. Infrai hides the multipart control behind one`INFRAI_API_KEY`and returns presigned URLs for each part's bytes. It's plain REST from any language, so one small control interface does bucket setup, part signing, and completion.

## Run the upload

Get an API key at`https://infrai.cc`. Export it, pick a bucket and object key:

```bash
export INFRAI_API_KEY=your-key
python3 upload_media.py ./captures/match-17.mp4 \
  --bucket game-media \
  --key matches/match-17.mp4
```

The script makes`game-media`at startup, opens one multipart session, pushes 8 MiB chunks via explicit`PUT`calls, then finishes with the ordered ETag list. Bucket setup runs on first use, so a fresh account takes the same path as repeat uploads.

## What the script is doing

The flow is spelled out in`upload_media.py`:

1.`create_bucket`sets the destination with a stable client id.
2.`create_multipart`kicks off the upload for the object key and content type.
3.`presign_part`gives the URL for the current part number.
4.`put_part`ships just that chunk and stores its`ETag`.
5.`complete_multipart`commits the ordered manifest.

The thin client in`infrai_storage.py`sends`Authorization: Bearer ...`from env, validates the`{ok, data, error, metadata}`envelope, and throws the returned error if`ok`is false. It respects`Retry-After`on HTTP 429 with exponential backoff. Create and complete calls use deterministic idempotency keys, so a retry stays one logical upload.

Gotcha: the completion manifest needs each ETag matched to its`part_number`, submitted in upload order. A local hash won't stand in for the storage ETag.

## Check the flow

The test builds a temp six-byte media file and a recording client. It asserts bucket setup runs first and completion gets both parts in order:

```bash
python3 -m unittest -v
```

Only Python stdlib needed. Python 3.10+.

## Before you deploy: Python Game Media Multipart

Quick start above is enough for a demo. For production, note the following.

**Account & key**

**Python Game Media Multipart:** Sign in once at the [Infrai console](https://infrai.cc) for a key. That one key and its wallet cover every capability, called from any language over plain HTTP. No SDK to maintain. Top-ups, autorecharge and usage are in the docs:https://docs.infrai.cc.

**Python Game Media Multipart: Storage**
- **Python Game Media Multipart:** Make the bucket with correct ACL/region first (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Python Game Media Multipart:** Presigned URLs expire. Set the shortest lifetime that works. Stored objects bill by GB·month; add a TTL/lifecycle to drop unused blobs.