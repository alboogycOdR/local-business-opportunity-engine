from pathlib import Path

import pytest
from lboe_api.storage import LocalArtifactStorage, ObjectStorageArtifactPlaceholder, artifact_ref


def test_local_storage_is_path_safe(tmp_path: Path) -> None:
    storage = LocalArtifactStorage(tmp_path)
    assert storage.put("demos/a/index.html", b"ok", "text/html").endswith("index.html")
    assert storage.exists("demos/a/index.html")
    with pytest.raises(ValueError):
        storage.put("../outside", b"no", "text/plain")
    assert artifact_ref("demos/a/index.html").startswith("artifact:")


def test_object_storage_requires_explicit_configuration() -> None:
    with pytest.raises(ValueError):
        ObjectStorageArtifactPlaceholder(None, None)
