"""Provider-neutral artifact storage with a safe local backend."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol


class ArtifactStorage(Protocol):
    def put(self, key: str, content: bytes, content_type: str) -> str: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...


class LocalArtifactStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root != path and self.root not in path.parents:
            raise ValueError("artifact_path_invalid")
        return path

    def put(self, key: str, content: bytes, content_type: str) -> str:
        del content_type
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()


class ObjectStorageArtifactPlaceholder:
    """Explicit placeholder until an S3/R2 SDK is approved for deployment."""

    def __init__(self, endpoint_url: str | None, bucket: str | None) -> None:
        if not endpoint_url or not bucket:
            raise ValueError("s3_endpoint_and_bucket_required")
        self.endpoint_url = endpoint_url
        self.bucket = bucket

    def put(self, key: str, content: bytes, content_type: str) -> str:
        del key, content, content_type
        raise NotImplementedError("object_storage_provider_not_configured")

    def exists(self, key: str) -> bool:
        del key
        raise NotImplementedError("object_storage_provider_not_configured")

    def delete(self, key: str) -> None:
        del key
        raise NotImplementedError("object_storage_provider_not_configured")


def artifact_ref(key: str) -> str:
    return "artifact:" + hashlib.sha256(key.encode()).hexdigest()
