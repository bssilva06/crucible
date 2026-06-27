from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from crucible.phase0.config import ConfigError, Phase0Settings


def object_key(run_id: str, filename: str, prefix: str = "runs/local") -> str:
    cleaned_prefix = prefix.strip("/")
    cleaned_filename = filename.strip("/")
    return f"{cleaned_prefix}/{run_id}/{cleaned_filename}"


def candidate_object_key(run_id: str, attempt_id: str, filename: str, prefix: str = "runs/local") -> str:
    cleaned_prefix = prefix.strip("/")
    cleaned_filename = filename.strip("/")
    cleaned_attempt_id = attempt_id.strip("/")
    return f"{cleaned_prefix}/{run_id}/candidates/{cleaned_attempt_id}/{cleaned_filename}"


@dataclass(frozen=True)
class StoredObject:
    uri: str
    key: str


class Storage:
    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        raise NotImplementedError

    def get_bytes(self, uri_or_key: str) -> bytes:
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, root: Path, bucket_name: str = "local") -> None:
        self.root = root
        self.bucket_name = bucket_name

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(uri=f"b2://{self.bucket_name}/{key}", key=key)

    def get_bytes(self, uri_or_key: str) -> bytes:
        key = parse_b2_uri(uri_or_key).key if uri_or_key.startswith("b2://") else uri_or_key
        return (self.root / key).read_bytes()


class B2Storage(Storage):
    def __init__(self, settings: Phase0Settings) -> None:
        settings.require_b2()
        try:
            import boto3
        except ImportError as exc:
            raise ConfigError("boto3 is required for live B2 storage. Install project dependencies.") from exc

        self.bucket_name = settings.b2_bucket_name or ""
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.b2_endpoint_url,
            aws_access_key_id=settings.b2_application_key_id,
            aws_secret_access_key=settings.b2_application_key,
            region_name=settings.b2_bucket_region,
        )

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        self._client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return StoredObject(uri=f"b2://{self.bucket_name}/{key}", key=key)

    def get_bytes(self, uri_or_key: str) -> bytes:
        parsed = parse_b2_uri(uri_or_key) if uri_or_key.startswith("b2://") else ParsedB2Uri(self.bucket_name, uri_or_key)
        response = self._client.get_object(Bucket=parsed.bucket, Key=parsed.key)
        return response["Body"].read()


@dataclass(frozen=True)
class ParsedB2Uri:
    bucket: str
    key: str


def parse_b2_uri(uri: str) -> ParsedB2Uri:
    parsed = urlparse(uri)
    if parsed.scheme != "b2" or not parsed.netloc or not parsed.path:
        raise ValueError(f"Expected b2://bucket/key URI, got {uri!r}")
    return ParsedB2Uri(bucket=parsed.netloc, key=parsed.path.lstrip("/"))
