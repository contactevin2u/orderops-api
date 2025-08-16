import os, uuid, io, boto3
from botocore.client import Config
from .settings import settings

s3 = None
if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY and settings.S3_BUCKET:
    s3 = boto3.client('s3', region_name=settings.AWS_DEFAULT_REGION or "ap-southeast-1",
                      aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                      config=Config(signature_version='s3v4'))

LOCAL_FILES_DIR = os.path.join(os.path.dirname(__file__), "..", "files")
os.makedirs(LOCAL_FILES_DIR, exist_ok=True)

def store_bytes(file_type: str, data: bytes, filename: str) -> str:
    if s3:
        key = f"{file_type}/{uuid.uuid4().hex}/{filename}"
        s3.upload_fileobj(io.BytesIO(data), settings.S3_BUCKET, key, ExtraArgs={"ContentType": "application/pdf"})
        return f"https://{settings.S3_BUCKET}.s3.amazonaws.com/{key}"
    else:
        subdir = os.path.join(LOCAL_FILES_DIR, file_type)
        os.makedirs(subdir, exist_ok=True)
        path = os.path.join(subdir, filename)
        with open(path, "wb") as f:
            f.write(data)
        return f"/files/{file_type}/{filename}"
