"""Storage errors."""

from __future__ import annotations


class AssetStorageError(RuntimeError):
    pass


class R2StorageUnavailableError(AssetStorageError):
    pass


class R2UploadError(AssetStorageError):
    pass
