"""Storage backend factory."""
from typing import Dict, Any, Optional
from . import StorageBackend
from .r2_backend import R2Backend
from .local_backend import LocalStorageBackend


_backend_cache: Dict[str, StorageBackend] = {}


def create_backend(config: Dict[str, Any]) -> StorageBackend:
    """Create storage backend from config."""
    backend_type = config.get("backend", "r2").lower()
    
    if backend_type == "r2":
        return R2Backend(config)
    elif backend_type == "s3":
        raise NotImplementedError("S3 backend not yet implemented")
    elif backend_type == "local":
        return LocalStorageBackend(config)
    else:
        raise ValueError(f"Unknown storage backend: {backend_type}")


def get_client_storage_backend(client_config: Dict[str, Any]) -> StorageBackend:
    """Get storage backend for a specific client."""
    if "backend" in client_config and client_config.get("backend"):
        # Direct config passed (backup router style)
        return create_backend(client_config)
    # Legacy config with nested backup_storage key
    storage_config = client_config.get("backup_storage", {})
    storage_config["backend"] = storage_config.get("backend", "r2")
    return create_backend(storage_config)


def get_storage_backend(config: Optional[Dict[str, Any]] = None) -> StorageBackend:
    """Get global storage backend instance (cached)."""
    if config is None:
        config = {"backend": "local"}
    backend_type = config.get("backend", "local")
    
    if backend_type not in _backend_cache:
        _backend_cache[backend_type] = create_backend(config)
    return _backend_cache[backend_type]

