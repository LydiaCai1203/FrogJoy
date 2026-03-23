#!/bin/bash
echo "Starting EPUB-TTS Backend..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found."
    exit 1
fi

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run server
echo "Starting FastAPI server on http://localhost:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
