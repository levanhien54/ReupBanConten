import hashlib
import os
from pathlib import Path
from src.core.logging import get_logger

logger = get_logger(__name__)

class VideoHasher:
    """
    Xác định danh tính video bằng mã băm SHA-256.
    Giúp hệ thống tránh xử lý lại các video đã tồn tại, tiết kiệm chi phí API.
    """
    
    def __init__(self, chunk_size: int = 65536):
        self.chunk_size = chunk_size

    def generate_hash(self, file_path: str | Path) -> str:
        """
        Tạo mã SHA-256 cho file video.
        
        Args:
            file_path: Đường dẫn tới file video.
            
        Returns:
            Chuỗi hash hex.
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File không tồn tại: {file_path}")
            raise FileNotFoundError(f"Video file not found: {file_path}")

        sha256 = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                while chunk := f.read(self.chunk_size):
                    sha256.update(chunk)
            
            file_hash = sha256.hexdigest()
            logger.info(f"Generated hash for {path.name}: {file_hash}")
            return file_hash
        except Exception as e:
            logger.error(f"Lỗi khi tạo hash cho {file_path}: {e}")
            raise

    def verify_hash(self, file_path: str | Path, expected_hash: str) -> bool:
        """Kiểm tra file có khớp với hash mong muốn không."""
        return self.generate_hash(file_path) == expected_hash
