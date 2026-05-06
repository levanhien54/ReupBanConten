"""
Meme Starter Pack Downloader — Tải bộ assets meme mặc định.
Cung cấp các âm thanh và hình ảnh phổ biến để bắt đầu ngay lập tức.
"""
import os
import urllib.request
from src.core.logging import get_logger

logger = get_logger(__name__)

MEME_ASSETS = {
    "sounds/funny": {
        "vine_boom.mp3": "https://www.myinstants.com/media/sounds/vine-boom.mp3",
        "bruh.mp3": "https://www.myinstants.com/media/sounds/bruh.mp3",
        "emotional_damage.mp3": "https://www.myinstants.com/media/sounds/emotional-damage-meme.mp3",
    },
    "sounds/hype": {
        "airhorn.mp3": "https://www.myinstants.com/media/sounds/air-horn-club-sample_1.mp3",
        "wow.mp3": "https://www.myinstants.com/media/sounds/anime-wow-sound-effect.mp3",
    },
    "images/reactions": {
        "shocked_pikachu.png": "https://i.imgur.com/8mB7u8I.png",
        "doge.png": "https://i.imgur.com/nS7xYyG.png",
    }
}

class MemeDownloader:
    """Tự động tải bộ meme mẫu."""

    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir

    def download_starter_pack(self) -> None:
        """Tải toàn bộ bộ meme mẫu nếu chưa tồn tại."""
        logger.info("Đang kiểm tra và tải bộ Meme Starter Pack...")
        
        for category, items in MEME_ASSETS.items():
            cat_dir = os.path.join(self.base_dir, category.replace("/", os.sep))
            os.makedirs(cat_dir, exist_ok=True)
            
            for name, url in items.items():
                dest = os.path.join(cat_dir, name)
                if not os.path.exists(dest):
                    try:
                        logger.info(f"Downloading meme: {name}...")
                        urllib.request.urlretrieve(url, dest)
                    except Exception as e:
                        logger.warning(f"Không thể tải meme {name}: {e}")
        
        logger.info("Hoàn tất tải bộ Meme Starter Pack.")
