#!/bin/bash
# run.sh - Chạy Chatbot TVTS trên máy mới tinh (chưa có gì)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Chatbot TVTS - Setup & Run ==="

# 1. Kiểm tra Python 3
if ! command -v python3 &>/dev/null; then
    echo "Lỗi: Cần cài Python 3. Chạy: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python: $PYTHON_VER"

# 2. Tạo virtual environment nếu chưa có
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Tạo virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# 3. Kích hoạt venv và cài dependencies
echo "Kích hoạt venv và cài dependencies..."
source "$VENV_DIR/bin/activate"

if [ ! -f "$VENV_DIR/.installed" ] || [ requirements.txt -nt "$VENV_DIR/.installed" ]; then
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    touch "$VENV_DIR/.installed"
    echo "Đã cài xong dependencies."
fi

# 4. Tạo .env từ .envexample nếu chưa có
if [ ! -f ".env" ]; then
    if [ -f ".envexample" ]; then
        cp .envexample .env
        echo "Đã tạo .env từ .envexample. Hãy chỉnh sửa .env (API key, MongoDB URI...) trước khi chạy."
    else
        echo "Lỗi: Không tìm thấy .envexample để tạo .env"
        exit 1
    fi
fi

# 5. Chạy app
echo ""
python3 sources/app.py
