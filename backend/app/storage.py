# backend/app/storage.py
"""Abstração de armazenamento de arquivos (Local ou S3/MinIO) com prevenção de Path Traversal."""

import os
from pathlib import Path
import re


def _sanitize_key(key: str) -> str:
    clean = (key or "").replace("\\", "/").lstrip("/")
    if not clean or ".." in clean.split("/") or "\x00" in clean:
        raise ValueError("Chave de armazenamento inválida.")
    parts = [re.sub(r"[^A-Za-z0-9_.-]", "_", p) for p in clean.split("/") if p]
    if not parts:
        raise ValueError("Chave de armazenamento vazia.")
    return "/".join(parts)


class LocalStorageBackend:
    def __init__(self, base_dir: str = "storage_data"):
        self.base_dir = os.path.realpath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def resolve_path(self, key: str) -> str:
        safe_key = _sanitize_key(key)
        dest = os.path.realpath(os.path.join(self.base_dir, *safe_key.split("/")))
        if os.path.commonpath([self.base_dir, dest]) != self.base_dir or dest == self.base_dir:
            raise ValueError("Caminho fora do diretório de armazenamento.")
        return dest

    def save_bytes(self, key: str, data: bytes) -> str:
        dest = self.resolve_path(key)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        return key

    def read_bytes(self, key: str) -> bytes:
        dest = self.resolve_path(key)
        with open(dest, "rb") as f:
            return f.read()

    def exists(self, key: str) -> bool:
        return os.path.isfile(self.resolve_path(key))


class S3StorageBackend:
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket: str):
        import boto3  # import sob demanda para não exigir boto3 quando usar storage local

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    def save_bytes(self, key: str, data: bytes) -> str:
        safe_key = _sanitize_key(key)
        self.client.put_object(Bucket=self.bucket, Key=safe_key, Body=data)
        return safe_key

    def get_presigned_url(self, key: str, expires_in: int = 60) -> str:
        safe_key = _sanitize_key(key)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": safe_key},
            ExpiresIn=expires_in,
        )


def get_storage():
    endpoint = os.getenv("S3_ENDPOINT_URL", "").strip()
    bucket = os.getenv("S3_BUCKET", "").strip()
    if endpoint and bucket:
        return S3StorageBackend(
            endpoint_url=endpoint,
            access_key=os.getenv("S3_ACCESS_KEY", ""),
            secret_key=os.getenv("S3_SECRET_KEY", ""),
            bucket=bucket,
        )
    return LocalStorageBackend(os.getenv("LOCAL_STORAGE_DIR", "storage_data"))
