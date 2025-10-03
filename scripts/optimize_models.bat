@echo off
REM Model Optimization Script for AI Math Tutor
REM Windows batch script for model quantization and GPU acceleration

echo ========================================
echo AI Math Tutor - Model Optimization Script
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

REM Activate virtual environment if it exists
if exist "..\venv" (
    echo Activating virtual environment...
    call ..\venv\Scripts\activate.bat
)

REM Check system requirements first
echo Checking system requirements...
python optimize_models.py system-info
echo.

REM Ask user what they want to do
echo Select an option:
echo 1. Get optimization recommendations
echo 2. Optimize all models (recommended)
echo 3. Optimize specific model
echo 4. Run quantization on all models
echo 5. Run pruning on all models
echo 6. Run distillation on all models
echo 7. Show optimization history
echo 8. Exit
echo.

set /p choice="Enter your choice (1-8): "

if "%choice%"=="1" (
    echo Getting optimization recommendations...
    python optimize_models.py recommendations
) else if "%choice%"=="2" (
    echo Optimizing all models...
    echo WARNING: This may take a long time
    echo.
    set /p confirm="Continue? (y/n): "
    if /i "%confirm%"=="y" (
        python optimize_models.py optimize all quantization
    ) else (
        echo Optimization cancelled
    )
) else if "%choice%"=="3" (
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

    echo Available optimization types:
    echo 1. Quantization (recommended)
    echo 2. Pruning
    echo 3. Distillation
    echo.
    set /p opt_choice="Enter optimization type (1-3): "

    if "%opt_choice%"=="1" (
        set opt_type=quantization
    ) else if "%opt_choice%"=="2" (
        set opt_type=pruning
    ) else if "%opt_choice%"=="3" (
        set opt_type=distillation
    ) else (
        echo Invalid choice
        pause
        exit /b 1
    )

    echo Optimizing %model_name% with %opt_type%...
    python optimize_models.py optimize %model_name% %opt_type%
) else if "%choice%"=="4" (
    echo Running quantization on all models...
    python optimize_models.py optimize all quantization
) else if "%choice%"=="5" (
    echo Running pruning on all models...
    python optimize_models.py optimize all pruning
) else if "%choice%"=="6" (
    echo Running distillation on all models...
    echo WARNING: Distillation may take a very long time
    echo.
    set /p confirm="Continue? (y/n): "
    if /i "%confirm%"=="y" (
        python optimize_models.py optimize all distillation
    ) else (
        echo Distillation cancelled
    )
) else if "%choice%"=="7" (
    echo Optimization history not implemented yet
    echo This would show previous optimization results
) else if "%choice%"=="8" (
    echo Exiting...
    exit /b 0
) else (
    echo Invalid choice
    pause
    exit /b 1
)

echo.
echo Optimization completed!
echo.
echo Next steps:
echo 1. Test optimized models in the application
echo 2. Monitor performance improvements
echo 3. Verify model accuracy is maintained
echo.

pause