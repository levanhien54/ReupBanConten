# 🚀 Hướng Dẫn Deploy - ReupBanConten

## Yêu Cầu Hệ Thống

### Tối thiểu
- **OS**: Windows 10/11, Ubuntu 20.04+, macOS 12+
- **CPU**: 4 cores
- **RAM**: 8 GB
- **Storage**: 20 GB trống
- **Python**: 3.11+
- **FFmpeg**: 6.0+

### Khuyến nghị (có GPU)
- **GPU**: NVIDIA RTX 3060+ (6GB VRAM)
- **RAM**: 16 GB
- **CUDA**: 12.0+
- **Storage**: 100 GB SSD (cho video cache)

---

## Cài Đặt Chi Tiết

### Windows

```powershell
# 1. Clone project
cd d:\ReupBanConten

# 2. Tạo virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Cài PyTorch (GPU)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# 4. Cài dependencies
pip install -r requirements.txt

# 5. Cài FFmpeg
winget install FFmpeg
# hoặc: scoop install ffmpeg

# 6. Cài Ollama
winget install Ollama.Ollama
ollama pull llama3
ollama pull mistral

# 7. Cấu hình
copy .env.example .env
# Chỉnh sửa .env

# 8. Khởi tạo database
python -m src.main init

# 9. Test
python -m pytest tests/
```

### Linux / macOS

```bash
# 1. Setup
cd /path/to/ReupBanConten
python3 -m venv venv
source venv/bin/activate

# 2. PyTorch
pip install torch torchaudio

# 3. Dependencies
pip install -r requirements.txt

# 4. FFmpeg
sudo apt install ffmpeg  # Ubuntu
brew install ffmpeg       # macOS

# 5. Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3
```

---

## Kiểm Tra Cài Đặt

```bash
# Kiểm tra FFmpeg
ffmpeg -version

# Kiểm tra Ollama
ollama list

# Kiểm tra GPU
python -c "import torch; print(torch.cuda.is_available())"

# Kiểm tra Whisper
python -c "from faster_whisper import WhisperModel; print('OK')"

# Chạy test suite
python -m pytest tests/ -v
```

---

## Build Executable (PyInstaller)

```bash
pip install pyinstaller

pyinstaller --name ReupBanConten \
    --onefile \
    --add-data "config:config" \
    --hidden-import ollama \
    --hidden-import faster_whisper \
    src/main.py
```

---

## Troubleshooting

| Vấn đề | Giải pháp |
|--------|-----------|
| CUDA out of memory | Dùng Whisper model nhỏ hơn (small/medium) |
| yt-dlp bị block | Cập nhật yt-dlp, dùng cookies/proxy |
| Ollama không kết nối | Kiểm tra `ollama serve` đang chạy |
| FFmpeg not found | Thêm FFmpeg vào PATH |
| Import error | Kiểm tra virtual env đã activate |
