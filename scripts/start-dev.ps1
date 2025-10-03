# AI Math Tutor Development Startup Script
# This script starts the development environment

param (
    [switch]$StartBackend = $true,
    [switch]$StartFrontend = $true,
    [switch]$OpenBrowser = $true,
    [string]$BackendHost = "localhost",
    [int]$BackendPort = 8000,
    [string]$FrontendHost = "localhost",
    [int]$FrontendPort = 3000
)

# Set variables
$ErrorActionPreference = "Continue"

Write-Host "🚀 Starting AI Math Tutor Development Environment" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Yellow
Write-Host ""

# Check if required files exist
if (-not (Test-Path "package.json")) {
    Write-Host "❌ package.json not found. Please run from project root." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "src\backend\main.py")) {
    Write-Host "❌ Backend main.py not found. Please check the project structure." -ForegroundColor Red
    exit 1
}

# Function to check if a port is available
function Test-Port {
    param ([int]$Port)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("localhost", $Port)
        $tcp.Close()
        return $false  # Port is in use
    } catch {
        return $true  # Port is available
    }
}

# Check port availability
Write-Host "🔍 Checking port availability..." -ForegroundColor Cyan

if (-not (Test-Port -Port $BackendPort)) {
    Write-Host "❌ Backend port $BackendPort is already in use" -ForegroundColor Red
    Write-Host "   Please stop the service using this port or use a different port." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Port -Port $FrontendPort)) {
    Write-Host "❌ Frontend port $FrontendPort is already in use" -ForegroundColor Red
    Write-Host "   Please stop the service using this port or use a different port." -ForegroundColor Yellow
    exit 1
}

Write-Host "  ✅ Ports $BackendPort and $FrontendPort are available" -ForegroundColor Green

# Start backend server
if ($StartBackend) {
    Write-Host "🐍 Starting backend server..." -ForegroundColor Cyan

    # Set environment variable for backend
    $env:PYTHONPATH = "$(Get-Location)\src\backend"

    # Start backend in a new window
    $backendScript = @"
cd "$(Get-Location)\src\backend"
python -m uvicorn main:app --reload --host $BackendHost --port $BackendPort
"@

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendScript -WindowStyle Normal
    Write-Host "  ✅ Backend server starting in new window" -ForegroundColor Green

    # Wait for backend to be ready
    Write-Host "⏳ Waiting for backend server to be ready..." -ForegroundColor Yellow
    $backendReady = $false
    $attempts = 0
    $maxAttempts = 30

    while (-not $backendReady -and $attempts -lt $maxAttempts) {
        try {
            $response = Invoke-RestMethod -Uri "http://$BackendHost`:$BackendPort/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.status -eq "healthy") {
                $backendReady = $true
                Write-Host "  ✅ Backend server is ready" -ForegroundColor Green
            }
        } catch {
            Write-Host "." -ForegroundColor Gray -NoNewline
            Start-Sleep -Seconds 1
        }
        $attempts++
    }

    if (-not $backendReady) {
        Write-Host "`n❌ Backend server failed to start within $maxAttempts seconds" -ForegroundColor Red
        Write-Host "   Please check the backend window for errors." -ForegroundColor Yellow
        exit 1
    }
}

# Start frontend development server
if ($StartFrontend) {
    Write-Host "⚛️  Starting frontend development server..." -ForegroundColor Cyan

    # Set environment variable for frontend
    $env:REACT_APP_BACKEND_URL = "http://$BackendHost`:$BackendPort"

    # Start frontend in a new window
    $frontendScript = @"
cd "$(Get-Location)"
npm run dev
"@

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendScript -WindowStyle Normal
    Write-Host "  ✅ Frontend server starting in new window" -ForegroundColor Green

    # Wait for frontend to be ready
    Write-Host "⏳ Waiting for frontend server to be ready..." -ForegroundColor Yellow
    $frontendReady = $false
    $attempts = 0
    $maxAttempts = 30

    while (-not $frontendReady -and $attempts -lt $maxAttempts) {
        try {
            $response = Invoke-RestMethod -Uri "http://$FrontendHost`:$FrontendPort" -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response) {
                $frontendReady = $true
                Write-Host "  ✅ Frontend server is ready" -ForegroundColor Green
            }
        } catch {
            Write-Host "." -ForegroundColor Gray -NoNewline
            Start-Sleep -Seconds 1
        }
        $attempts++
    }

    if (-not $frontendReady) {
        Write-Host "`n❌ Frontend server failed to start within $maxAttempts seconds" -ForegroundColor Red
        Write-Host "   Please check the frontend window for errors." -ForegroundColor Yellow
        exit 1
    }
}

# Open browser
if ($OpenBrowser) {
    Write-Host "🌐 Opening browser..." -ForegroundColor Cyan
    Start-Sleep -Seconds 2
    Start-Process "http://$FrontendHost`:$FrontendPort"
    Write-Host "  ✅ Browser opened" -ForegroundColor Green
}

# Display summary
Write-Host ""
Write-Host "🎉 Development environment is ready!" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Yellow
Write-Host ""

Write-Host "📱 Frontend:" -ForegroundColor Cyan
Write-Host "   URL: http://$FrontendHost`:$FrontendPort" -ForegroundColor White
Write-Host "   Window: React development server" -ForegroundColor White

Write-Host ""
Write-Host "🔧 Backend:" -ForegroundColor Cyan
Write-Host "   URL: http://$BackendHost`:$BackendPort" -ForegroundColor White
Write-Host "   API Docs: http://$BackendHost`:$BackendPort/api/docs" -ForegroundColor White
Write-Host "   Health: http://$BackendHost`:$BackendPort/health" -ForegroundColor White
Write-Host "   Window: Python FastAPI server" -ForegroundColor White

Write-Host ""
Write-Host "🛠️  Development Tools:" -ForegroundColor Cyan
Write-Host "   - Backend logs: Check the Python window" -ForegroundColor White
Write-Host "   - Frontend logs: Check the React window" -ForegroundColor White
Write-Host "   - Hot reload: Enabled for both frontend and backend" -ForegroundColor White
Write-Host "   - API testing: Use the API docs at /api/docs" -ForegroundColor White

Write-Host ""
Write-Host "📝 Useful Commands:" -ForegroundColor Cyan
Write-Host "   - npm run lint: Run ESLint" -ForegroundColor White
Write-Host "   - npm run test: Run tests" -ForegroundColor White
Write-Host "   - npm run build: Build for production" -ForegroundColor White
Write-Host "   - Press Ctrl+C in each window to stop the servers" -ForegroundColor White

Write-Host ""
Write-Host "🔄 To restart:" -ForegroundColor Cyan
Write-Host "   1. Close the existing windows" -ForegroundColor White
Write-Host "   2. Run this script again" -ForegroundColor White

Write-Host ""
Write-Host "Happy coding! 🚀" -ForegroundColor Green

# Keep the script running
if ($StartBackend -or $StartFrontend) {
    Write-Host ""
    Write-Host "ℹ️  Press Enter to exit this setup script (servers will continue running)" -ForegroundColor Yellow
    Read-Host | Out-Null
}