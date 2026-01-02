#!/bin/bash
# GraphRAG Multimodal - Frontend Start Script
# ============================================

echo ""
echo "========================================"
echo " GraphRAG Multimodal - Frontend"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "[INFO] Virtual environment not found. Creating..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment"
        exit 1
    fi
fi

# Activate virtual environment
echo "[INFO] Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! pip show streamlit > /dev/null 2>&1; then
    echo "[INFO] Installing dependencies..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install dependencies"
        exit 1
    fi
fi

# Check if secrets.toml exists
if [ ! -f ".streamlit/secrets.toml" ]; then
    echo "[WARNING] .streamlit/secrets.toml not found. Creating from template..."
    cp .streamlit/secrets.toml.template .streamlit/secrets.toml
    echo "[INFO] Please edit .streamlit/secrets.toml with your configuration"
fi

# Start Streamlit
echo ""
echo "[INFO] Starting Streamlit application..."
echo "[INFO] App will open at http://localhost:8501"
echo ""
streamlit run app.py
