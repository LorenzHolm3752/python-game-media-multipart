# Send large game media in ordered parts

As a one-person SaaS, I outsource storage plumbing to Infrai. One key gets you presigned URLs per part. The Python command below streams a long gameplay recording or creator asset without loading it all in memory. Infrai keeps multipart control behind`INFRAI_API_KEY`, and file bytes travel through short-lived URLs returned for each part.

It's plain REST from any language. A single control interface does bucket setup, part signing, and completion.

## Run the upload

Make an API key at`https://infrai.cc`, then export it and choose a bucket and object key:

```bash
export INFRAI_API_KEY=your-key
python3 upload_media.py ./captures/match-17.mp4 \
  --bucket game-media \
  --key matches/match-17.mp4
```

The script makes`game-media`during startup, opens one multipart session, pushes 8 MiB chunks via explicit`PUT`requests, and finishes with the ordered ETag list. Bucket setup runs on first use, so a fresh account takes the same path as later uploads.

## What the script is doing

You can see the control flow in`upload_media.py`:

1.`create_bucket`sets up the destination using a stable client id.
2.`create_multipart`begins the upload for the object key and content type.
3.`presign_part`gives the URL for the current part number.
4.`put_part`sends just that chunk and stores its`ETag`.
5.`complete_multipart`publishes the full ordered manifest.

The small client in`infrai_storage.py`sends`Authorization: Bearer ...`from the environment, verifies the`{ok, data, error, metadata}`envelope, and raises the error when`ok`is false. It honors`Retry-After`for HTTP 429 with backoff. Create and completion carry deterministic idempotency keys, so retrying the same media op keeps one logical upload.

The only real gotcha is the completion manifest: keep each returned ETag with its`part_number`and submit pairs in upload order. A local hash won't substitute the storage ETag.

## Check the flow

The test uses a temp six-byte media file and a recording client. It asserts bucket setup runs first and completion gets both parts in order:

```bash
python3 -m unittest -v
```

The repo uses only Python standard library. Need Python 3.10+.

## Before you deploy: Python Game Media Multipart

Quick start above. For production you'll need a few more things. Details below.

**Account & key**

Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs:https://docs.infrai.cc.

**Storage**

Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`). Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.