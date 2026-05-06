import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Dict, Optional, Any
from src.core.logging import get_logger

logger = get_logger(__name__)

class VectorStore:
    """
    Quản lý Vector Database (ChromaDB) để tìm kiếm nội dung video theo ngữ nghĩa.
    """
    
    def __init__(self, persist_directory: str | Path):
        self.persist_directory = str(persist_directory)
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="video_clips",
            metadata={"hnsw:space": "cosine"} # Dùng cosine similarity cho embeddings
        )

    def add_clip(self, clip_id: str, embedding: list[float], metadata: dict):
        """Thêm một clip vào vector store."""
        try:
            self.collection.add(
                ids=[clip_id],
                embeddings=[embedding],
                metadatas=[metadata]
            )
            logger.debug(f"Added clip {clip_id} to VectorStore")
        except Exception as e:
            logger.error(f"Lỗi khi thêm clip vào VectorStore: {e}")

    def search_clips(self, query_embedding: list[float], limit: int = 10, filters: dict = None) -> list[dict]:
        """Tìm kiếm các clips tương đồng nhất."""
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=filters
            )
            
            formatted_results = []
            for i in range(len(results["ids"][0])):
                formatted_results.append({
                    "id": results["ids"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i]
                })
            return formatted_results
        except Exception as e:
            logger.error(f"Lỗi khi tìm kiếm trong VectorStore: {e}")
            return []

    def count(self) -> int:
        return self.collection.count()
