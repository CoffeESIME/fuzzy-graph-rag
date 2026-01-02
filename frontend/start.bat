@echo off
REM GraphRAG Multimodal - Frontend Start Script
REM ============================================

echo.
echo ========================================
echo  GraphRAG Multimodal - Frontend
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo [INFO] Virtual environment not found. Creating...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if dependencies are installed
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
)

REM Check if secrets.toml exists
if not exist ".streamlit\secrets.toml" (
    echo [WARNING] .streamlit\secrets.toml not found. Creating from template...
    copy .streamlit\secrets.toml.template .streamlit\secrets.toml
    echo [INFO] Please edit .streamlit\secrets.toml with your configuration
)

REM Start Streamlit
echo.
echo [INFO] Starting Streamlit application...
echo [INFO] App will open at http://localhost:8501
echo.
streamlit run app.py

pause
