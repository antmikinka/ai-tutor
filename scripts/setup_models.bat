@echo off
REM Model Setup Script for AI Math Tutor
REM Windows batch script for downloading and setting up AI models

echo ========================================
echo AI Math Tutor - Model Setup Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

REM Check if running in correct directory
if not exist "..\src\backend" (
    echo ERROR: Script must be run from the scripts directory
    echo Current directory: %CD%
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "..\venv" (
    echo Creating virtual environment...
    python -m venv ..\venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully
)

REM Activate virtual environment
echo Activating virtual environment...
call ..\venv\Scripts\activate.bat

REM Install required packages
echo Installing required packages...
pip install -r ..\requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install required packages
    pause
    exit /b 1
)

REM Check system requirements
echo Checking system requirements...
python -c "import psutil; print(f'Memory: {psutil.virtual_memory().total / (1024**3):.1f} GB')"
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

REM Ask user what they want to do
echo.
echo Select an option:
echo 1. Setup all models (recommended)
echo 2. Setup specific model
echo 3. List downloaded models
echo 4. Check model status
echo 5. Cleanup old models
echo 6. Exit
echo.

set /p choice="Enter your choice (1-6): "

if "%choice%"=="1" (
    echo Setting up all models...
    echo WARNING: This may take a long time and require significant disk space
    echo.
    set /p confirm="Continue? (y/n): "
    if /i "%confirm%"=="y" (
        python setup_models.py
    ) else (
        echo Setup cancelled
    )
) else if "%choice%"=="2" (
    echo Available models:
    echo 1. Qwen3-Omni-30B-A3B-Thinking (Reasoning)
    echo 2. Microsoft-VibeVoice-1.5B (TTS)
    echo 3. MERaLiON-AudioLLM-Whisper-SEA-LION (STT)
    echo.
    set /p model_choice="Enter model number (1-3): "

    if "%model_choice%"=="1" (
        set model_name=Qwen3-Omni-30B-A3B-Thinking
    ) else if "%model_choice%"=="2" (
        set model_name=Microsoft-VibeVoice-1.5B
    ) else if "%model_choice%"=="3" (
        set model_name=MERaLiON-AudioLLM-Whisper-SEA-LION
    ) else (
        echo Invalid choice
        pause
        exit /b 1
    )

    echo Setting up %model_name%...
    set /p force_download="Force re-download? (y/n): "

    if /i "%force_download%"=="y" (
        python setup_models.py --model %model_name% --force
    ) else (
        python setup_models.py --model %model_name%
    )
) else if "%choice%"=="3" (
    echo Downloaded models:
    python setup_models.py --list
) else if "%choice%"=="4" (
    set /p model_name="Enter model name: "
    python setup_models.py --status %model_name%
) else if "%choice%"=="5" (
    echo Cleaning up old models...
    python setup_models.py --cleanup
) else if "%choice%"=="6" (
    echo Exiting...
    exit /b 0
) else (
    echo Invalid choice
    pause
    exit /b 1
)

echo.
echo Setup completed!
echo.
echo Next steps:
echo 1. Start the backend server: python ..\src\backend\main.py
echo 2. Start the frontend application
echo 3. Verify models are loaded in the application settings
echo.

pause