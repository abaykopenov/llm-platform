"""
File Store — Manages file metadata and original file storage on NFS.
"""

import hashlib
import json
import os
import time
from typing import List, Dict, Optional


class FileStore:
    """Stores file metadata and originals on disk (NFS mount)."""

    def __init__(
        self,
        upload_dir: str = "/data/uploads",
        default_collection: str = "general",
    ):
        self.upload_dir = upload_dir
        self.default_collection = default_collection
        self.meta_path = os.path.join(upload_dir, "_metadata.json")
        os.makedirs(upload_dir, exist_ok=True)
        self._meta = self._load_meta()

    def save_file(
        self,
        file_data: bytes,
        original_name: str,
        collection: str = "",
        chunks_count: int = 0,
    ) -> Dict:
        """Save file data and metadata. Returns file metadata dict."""
        collection = collection or self.default_collection
        file_id = "file_" + hashlib.md5(
            f"{original_name}_{time.time()}".encode()
        ).hexdigest()[:12]

        # Save original file
        file_dir = os.path.join(self.upload_dir, file_id)
        os.makedirs(file_dir, exist_ok=True)
        file_path = os.path.join(file_dir, original_name)
        with open(file_path, "wb") as f:
            f.write(file_data)

        # Save metadata
        meta = {
            "file_id": file_id,
            "original_name": original_name,
            "collection": collection,
            "chunks_count": chunks_count,
            "size_bytes": len(file_data),
            "ingested_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "file_path": file_path,
        }

        self._meta[file_id] = meta
        self._save_meta()

        return meta

    def list_files(self, collection: Optional[str] = None) -> List[Dict]:
        """List all files, optionally filtered by collection."""
        files = list(self._meta.values())
        if collection:
            files = [f for f in files if f.get("collection") == collection]
        return files

    def get_file(self, file_id: str) -> Optional[Dict]:
        """Get file metadata by ID."""
        return self._meta.get(file_id)

    def delete_file(self, file_id: str) -> bool:
        """Delete file metadata and original file."""
        if file_id not in self._meta:
            return False

        meta = self._meta[file_id]
        file_path = meta.get("file_path", "")

        # Delete original file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        # Clean up directory
        file_dir = os.path.join(self.upload_dir, file_id)
        if os.path.isdir(file_dir):
            try:
                os.rmdir(file_dir)
            except OSError:
                pass

        # Remove metadata
        del self._meta[file_id]
        self._save_meta()
        return True

    def _load_meta(self) -> Dict:
        """Load metadata from JSON file."""
        if os.path.exists(self.meta_path):
            try:
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_meta(self):
        """Save metadata to JSON file."""
        try:
            with open(self.meta_path, "w", encoding="utf-8") as f:
                json.dump(self._meta, f, ensure_ascii=False, indent=2)
        except IOError:
            pass
