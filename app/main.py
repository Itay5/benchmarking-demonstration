import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from starlette.responses import StreamingResponse
from google.cloud import storage

BUCKET = os.getenv("BUCKET_NAME")
if not BUCKET:
    raise RuntimeError("BUCKET_NAME env var is required")

client = storage.Client()
bucket = client.bucket(BUCKET)

app = FastAPI(title="Cloud‑Run + GCS demo")

@app.get("/")
def index():
    return {"msg": "Upload with POST /upload and download with GET /download/{file}"}

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    blob = bucket.blob(file.filename)
    blob.upload_from_file(file.file, content_type=file.content_type)
    return {"status": "ok", "file": file.filename}

@app.get("/download/{name}")
def download(name: str):
    blob = bucket.blob(name)
    if not blob.exists():
        raise HTTPException(404, "file not found")
    stream = blob.open("rb")
    return StreamingResponse(stream, media_type=blob.content_type or "application/octet-stream") 