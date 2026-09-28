# Artifact storage

`ArtifactStorage` and `LocalArtifactStorage` provide path-safe artifact writes,
existence checks, and deletion. Audit screenshots, demo assets, and exports are
local by default. `ObjectStorageArtifactPlaceholder` validates S3/R2 endpoint
and bucket configuration but intentionally does not claim a provider SDK is
configured. Credentials are environment-only.
