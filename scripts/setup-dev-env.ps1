# AI Math Tutor Development Environment Setup Script for Windows
# This script sets up the development environment for the AI Math Tutor application

param (
    [string]$PythonVersion = "3.11",
    [string]$NodeVersion = "18",
    [switch]$SkipPython = $false,
    [switch]$SkipNode = $false,
    [switch]$SkipModels = $false
)

Write-Host "🚀 Setting up AI Math Tutor Development Environment" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Yellow

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "⚠️  Running without administrator privileges. Some operations may require elevated permissions." -ForegroundColor Yellow
}

# Create necessary directories
Write-Host "📁 Creating directory structure..." -ForegroundColor Cyan
$directories = @(
    "logs",
    "temp",
    "uploads",
    "models",
    "models\cache",
    "src\backend\logs",
    "src\backend\temp",
    "src\backend\uploads"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Gray
    }
}

# Install Node.js if not already installed
if (-not $SkipNode) {
    Write-Host "📦 Checking Node.js installation..." -ForegroundColor Cyan

    try {
        $nodeVersion = node --version 2>$null
        if ($nodeVersion) {
            Write-Host "  ✅ Node.js $nodeVersion is already installed" -ForegroundColor Green
        } else {
            Write-Host "  ❌ Node.js is not installed" -ForegroundColor Red
            Write-Host "  Please install Node.js $NodeVersion or higher from https://nodejs.org/" -ForegroundColor Yellow
            Write-Host "  Then run this script again with -SkipNode flag" -ForegroundColor Yellow
            exit 1
        }
    } catch {
        Write-Host "  ❌ Node.js is not installed" -ForegroundColor Red
        Write-Host "  Please install Node.js $NodeVersion or higher from https://nodejs.org/" -ForegroundColor Yellow
        exit 1
    }

    # Install npm dependencies
    Write-Host "📦 Installing Node.js dependencies..." -ForegroundColor Cyan
    try {
        npm install
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ Node.js dependencies installed successfully" -ForegroundColor Green
        } else {
            Write-Host "  ❌ Failed to install Node.js dependencies" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "  ❌ Failed to install Node.js dependencies: $_" -ForegroundColor Red
        exit 1
    }

    # Install renderer dependencies
    Write-Host "📦 Installing renderer dependencies..." -ForegroundColor Cyan
    try {
        Push-Location src\renderer
        npm install
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ Renderer dependencies installed successfully" -ForegroundColor Green
        } else {
            Write-Host "  ❌ Failed to install renderer dependencies" -ForegroundColor Red
            Pop-Location
            exit 1
        }
        Pop-Location
    } catch {
        Write-Host "  ❌ Failed to install renderer dependencies: $_" -ForegroundColor Red
        Pop-Location
        exit 1
    }
}

# Install Python if not already installed
if (-not $SkipPython) {
    Write-Host "🐍 Checking Python installation..." -ForegroundColor Cyan

    try {
        $pythonVersion = python --version 2>$null
        if ($pythonVersion -match "Python 3\.[0-9]+") {
            Write-Host "  ✅ $pythonVersion is already installed" -ForegroundColor Green
        } else {
            Write-Host "  ❌ Python 3.x is not installed or not in PATH" -ForegroundColor Red
            Write-Host "  Please install Python $PythonVersion or higher from https://python.org/" -ForegroundColor Yellow
            Write-Host "  Make sure to check 'Add Python to PATH' during installation" -ForegroundColor Yellow
            Write-Host "  Then run this script again with -SkipPython flag" -ForegroundColor Yellow
            exit 1
        }
    } catch {
        Write-Host "  ❌ Python is not installed" -ForegroundColor Red
        Write-Host "  Please install Python $PythonVersion or higher from https://python.org/" -ForegroundColor Yellow
        Write-Host "  Make sure to check 'Add Python to PATH' during installation" -ForegroundColor Yellow
        exit 1
    }

    # Install Python dependencies
    Write-Host "📦 Installing Python dependencies..." -ForegroundColor Cyan
    try {
        Push-Location src\backend
        python -m pip install --upgrade pip
        python -m pip install -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ Python dependencies installed successfully" -ForegroundColor Green
        } else {
            Write-Host "  ❌ Failed to install Python dependencies" -ForegroundColor Red
            Pop-Location
            exit 1
        }
        Pop-Location
    } catch {
        Write-Host "  ❌ Failed to install Python dependencies: $_" -ForegroundColor Red
        Pop-Location
        exit 1
    }
}

# Create environment configuration
Write-Host "⚙️  Creating environment configuration..." -ForegroundColor Cyan
try {
    $envConfigPath = ".env"
    if (-not (Test-Path $envConfigPath)) {
        Copy-Item ".env.example" $envConfigPath -ErrorAction SilentlyContinue
        Write-Host "  ✅ Environment configuration created" -ForegroundColor Green
    } else {
        Write-Host "  ℹ️  Environment configuration already exists" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ⚠️  Could not create environment configuration: $_" -ForegroundColor Yellow
}

# Setup models (placeholder - would download actual models in production)
if (-not $SkipModels) {
    Write-Host "🤖 Setting up AI models..." -ForegroundColor Cyan
    Write-Host "  ℹ️  Model setup placeholder - models would be downloaded here in production" -ForegroundColor Yellow

    # Create model directories
    $modelDirs = @(
        "models\whisper",
        "models\tts",
        "models\qwen",
        "models\cache\whisper",
        "models\cache\tts",
        "models\cache\qwen"
    )

    foreach ($dir in $modelDirs) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }

    Write-Host "  ✅ Model directories created" -ForegroundColor Green
}

# Create development scripts
Write-Host "📜 Creating development scripts..." -ForegroundColor Cyan
$scripts = @(
    @{
        Name = "start-dev.ps1"
        Content = @'
# Development startup script
Write-Host "🚀 Starting AI Math Tutor in development mode..." -ForegroundColor Green

# Start backend server in background
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd src\backend; python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

# Wait for backend to start
Write-Host "⏳ Waiting for backend server to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Start frontend in development mode
npm run dev
'@
    },
    @{
        Name = "build-all.ps1"
        Content = @'
# Build script for all components
Write-Host "🏗️  Building AI Math Tutor..." -ForegroundColor Green

# Build React frontend
Write-Host "📦 Building frontend..." -ForegroundColor Cyan
Push-Location src\renderer
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Frontend build failed" -ForegroundColor Red
    exit 1
}
Pop-Location

# Build Electron application
Write-Host "📦 Building Electron application..." -ForegroundColor Cyan
npm run build

Write-Host "✅ Build completed successfully!" -ForegroundColor Green
'@
    },
    @{
        Name = "test-all.ps1"
        Content = @'
# Test script for all components
Write-Host "🧪 Running tests..." -ForegroundColor Green

# Run frontend tests
Write-Host "🧪 Running frontend tests..." -ForegroundColor Cyan
Push-Location src\renderer
npm test
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Frontend tests failed" -ForegroundColor Red
}
Pop-Location

# Run backend tests (if any)
Write-Host "🧪 Running backend tests..." -ForegroundColor Cyan
Push-Location src\backend
if (Test-Path "tests") {
    python -m pytest tests/ -v
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Backend tests failed" -ForegroundColor Red
    }
} else {
    Write-Host "ℹ️  No backend tests found" -ForegroundColor Yellow
}
Pop-Location

Write-Host "✅ Tests completed!" -ForegroundColor Green
'@
    }
)

foreach ($script in $scripts) {
    $scriptPath = "scripts\$($script.Name)"
    $script.Content | Out-File -FilePath $scriptPath -Encoding UTF8
    Write-Host "  Created: $scriptPath" -ForegroundColor Gray
}

# Create git pre-commit hook
Write-Host "🔗 Setting up git pre-commit hook..." -ForegroundColor Cyan
$hooksDir = ".git\hooks"
if (Test-Path $hooksDir) {
    $preCommitHook = @"
# Pre-commit hook for AI Math Tutor
Write-Host "🔍 Running pre-commit checks..." -ForegroundColor Yellow

# Run linting
Write-Host "📝 Running ESLint..." -ForegroundColor Cyan
npm run lint
if (`$LASTEXITCODE -ne 0) {
    Write-Host "❌ ESLint failed" -ForegroundColor Red
    exit 1
}

# Run tests if available
if (Test-Path "scripts\test-all.ps1") {
    & ".\scripts\test-all.ps1"
    if (`$LASTEXITCODE -ne 0) {
        Write-Host "❌ Tests failed" -ForegroundColor Red
        exit 1
    }
}

Write-Host "✅ Pre-commit checks passed!" -ForegroundColor Green
"@

    $preCommitHook | Out-File -FilePath "$hooksDir\pre-commit" -Encoding UTF8
    Write-Host "  ✅ Pre-commit hook created" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Git repository not initialized, skipping pre-commit hook" -ForegroundColor Yellow
}

# Create development documentation
Write-Host "📚 Creating development documentation..." -ForegroundColor Cyan
$docs = @(
    @{
        Name = "DEVELOPMENT.md"
        Content = @'
# AI Math Tutor Development Guide

## Prerequisites

- Node.js 18+
- Python 3.11+
- Windows 10 or later

## Setup

1. Run the setup script:
   ```powershell
   .\scripts\setup-dev-env.ps1
   ```

2. Start development server:
   ```powershell
   .\scripts\start-dev.ps1
   ```

## Development Commands

- `npm run dev` - Start development mode
- `npm run build` - Build for production
- `npm run test` - Run tests
- `npm run lint` - Run ESLint

## Project Structure

```
ai-llm-swift-app/
├── src/
│   ├── main/          # Electron main process
│   ├── renderer/      # React frontend
│   └── backend/       # Python FastAPI backend
├── assets/           # Application assets
├── scripts/          # Development scripts
└── models/           # AI model files
```

## API Documentation

- Frontend runs on: http://localhost:3000
- Backend API runs on: http://localhost:8000
- API docs: http://localhost:8000/api/docs
'@
    }
)

foreach ($doc in $docs) {
    $docPath = $doc.Name
    $doc.Content | Out-File -FilePath $docPath -Encoding UTF8
    Write-Host "  Created: $docPath" -ForegroundColor Gray
}

# Final summary
Write-Host ""
Write-Host "🎉 Development environment setup completed!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Run '.\scripts\start-dev.ps1' to start development" -ForegroundColor White
Write-Host "2. Open http://localhost:3000 in your browser" -ForegroundColor White
Write-Host "3. Backend API docs: http://localhost:8000/api/docs" -ForegroundColor White
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host "- npm run dev          - Start development server" -ForegroundColor White
Write-Host "- npm run build        - Build for production" -ForegroundColor White
Write-Host "- npm run test         - Run tests" -ForegroundColor White
Write-Host "- npm run lint         - Run ESLint" -ForegroundColor White
Write-Host ""
Write-Host "Happy coding! 🚀" -ForegroundColor Green