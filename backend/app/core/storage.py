import os
import hashlib
import shutil
from pathlib import Path
from typing import Tuple, Optional
from app.core.config import settings

class StorageService:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.STORAGE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def calculate_hash(self, file_bytes: bytes) -> str:
        """Calculate SHA256 hash of file content."""
        hasher = hashlib.sha256()
        hasher.update(file_bytes)
        return hasher.hexdigest()

    def save_file(self, file_bytes: bytes, original_filename: str) -> Tuple[str, str, int]:
        """
        Save file to persistent local storage using a content-addressed naming scheme.
        Returns: (stored_filename, sha256_hash, file_size_bytes)
        """
        file_hash = self.calculate_hash(file_bytes)
        file_size = len(file_bytes)
        
        # Clean extension
        suffix = Path(original_filename).suffix.lower()
        if not suffix:
            suffix = ".pdf"
            
        stored_filename = f"{file_hash[:16]}_{Path(original_filename).stem[:30]}{suffix}"
        # Prevent any path traversal
        stored_filename = "".join(c for c in stored_filename if c.isalnum() or c in "._-")
        target_path = self.base_dir / stored_filename
        
        # Atomic write
        temp_path = self.base_dir / f"{stored_filename}.tmp"
        with open(temp_path, "wb") as f:
            f.write(file_bytes)
        shutil.move(temp_path, target_path)
        
        return stored_filename, file_hash, file_size

    def get_file_path(self, stored_filename: str) -> Optional[Path]:
        """Get absolute path of stored file, validating it stays within storage directory."""
        clean_name = "".join(c for c in stored_filename if c.isalnum() or c in "._-")
        path = (self.base_dir / clean_name).resolve()
        
        # Security check: must reside inside base_dir
        if not str(path).startswith(str(self.base_dir.resolve())):
            return None
            
        if path.exists() and path.is_file():
            return path
        return None

    def read_file(self, stored_filename: str) -> Optional[bytes]:
        """Read file contents safely."""
        path = self.get_file_path(stored_filename)
        if path:
            with open(path, "rb") as f:
                return f.read()
        return None

    def delete_file(self, stored_filename: str) -> bool:
        """Delete file if it exists."""
        path = self.get_file_path(stored_filename)
        if path and path.exists():
            path.unlink()
            return True
        return False

storage_service = StorageService()
