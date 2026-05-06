import sys
import os
import asyncio
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Đảm bảo import đúng
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.config import get_config
from src.core.database import get_database, VideoRepository, ClipRepository
from src.ui.pages.dashboard import DashboardPage
from src.ui.pages.cutter import CutterPage
from src.ui.pages.analyzer import AnalyzerPage
from src.ui.pages.remixer import RemixerPage

def run_validation():
    print("Khoi chay bai kiem tra tich hop UI - Backend...")
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
        
    config = get_config()
    db = get_database()
    video_repo = VideoRepository(db)
    clip_repo = ClipRepository(db)
    
    print("\n--- 1. Kiem tra DashboardPage ---")
    try:
        dashboard = DashboardPage(config)
        dashboard._refresh_stats()
        print("OK: DashboardPage khoi tao va query database thanh cong.")
    except Exception as e:
        print(f"ERROR DashboardPage: {e}")

    print("\n--- 2. Kiem tra CutterPage ---")
    try:
        cutter = CutterPage(config)
        print("OK: CutterPage khoi tao thanh cong.")
    except Exception as e:
        print(f"ERROR CutterPage: {e}")

    print("\n--- 3. Kiem tra AnalyzerPage ---")
    try:
        analyzer = AnalyzerPage(config)
        print("OK: AnalyzerPage khoi tao thanh cong.")
    except Exception as e:
        print(f"ERROR AnalyzerPage: {e}")

    print("\n--- 4. Kiem tra RemixerPage ---")
    try:
        remixer = RemixerPage(config)
        remixer._load_mock_folders()
        print("OK: RemixerPage khoi tao va quet thu muc thanh cong.")
    except Exception as e:
        print(f"ERROR RemixerPage: {e}")

    print("\nTat ca bai kiem tra tich hop da hoan tat!")

if __name__ == "__main__":
    run_validation()
