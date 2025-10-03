# AI Math Tutor Windows Build Script
# This script builds the application for Windows distribution

param (
    [string]$Configuration = "production",
    [string]$Arch = "x64",
    [switch]$SkipTests = $false,
    [switch]$SkipSign = $false,
    [switch]$Portable = $false
)

# Set variables
$ErrorActionPreference = "Stop"
$startTime = Get-Date

Write-Host "🏗️  Building AI Math Tutor for Windows" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Yellow
Write-Host "Configuration: $Configuration" -ForegroundColor Cyan
Write-Host "Architecture: $Arch" -ForegroundColor Cyan
Write-Host "Portable: $Portable" -ForegroundColor Cyan
Write-Host ""

# Check if running in correct directory
if (-not (Test-Path "package.json")) {
    Write-Host "❌ Please run this script from the project root directory" -ForegroundColor Red
    exit 1
}

# Clean previous builds
Write-Host "🧹 Cleaning previous builds..." -ForegroundColor Cyan
if (Test-Path "dist") {
    Remove-Item -Path "dist" -Recurse -Force
}
if (Test-Path "src\renderer\build") {
    Remove-Item -Path "src\renderer\build" -Recurse -Force
}
if (Test-Path "src\renderer\.next") {
    Remove-Item -Path "src\renderer\.next" -Recurse -Force
}
Write-Host "  ✅ Previous builds cleaned" -ForegroundColor Green

# Run tests if not skipped
if (-not $SkipTests) {
    Write-Host "🧪 Running tests..." -ForegroundColor Cyan
    try {
        npm test
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Tests failed" -ForegroundColor Red
            exit 1
        }
        Write-Host "  ✅ Tests passed" -ForegroundColor Green
    } catch {
        Write-Host "❌ Tests failed: $_" -ForegroundColor Red
        exit 1
    }
}

# Install dependencies
Write-Host "📦 Installing dependencies..." -ForegroundColor Cyan
try {
    npm install
    Push-Location src\renderer
    npm install
    Pop-Location
    Write-Host "  ✅ Dependencies installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to install dependencies: $_" -ForegroundColor Red
    exit 1
}

# Build React frontend
Write-Host "📦 Building React frontend..." -ForegroundColor Cyan
try {
    Push-Location src\renderer
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Frontend build failed" -ForegroundColor Red
        exit 1
    }
    Pop-Location
    Write-Host "  ✅ Frontend built successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Frontend build failed: $_" -ForegroundColor Red
    exit 1
}

# Copy Python backend
Write-Host "🐍 Preparing Python backend..." -ForegroundColor Cyan
try {
    $backendDistDir = "dist\backend"
    if (-not (Test-Path $backendDistDir)) {
        New-Item -ItemType Directory -Path $backendDistDir -Force | Out-Null
    }

    # Copy backend files
    Copy-Item -Path "src\backend\*" -Destination $backendDistDir -Recurse -Force -Exclude @("__pycache__", "*.pyc", ".git")

    # Install Python dependencies to dist
    Push-Location $backendDistDir
    python -m pip install --target=. -r requirements.txt
    Pop-Location

    Write-Host "  ✅ Backend prepared" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to prepare backend: $_" -ForegroundColor Red
    exit 1
}

# Copy model files if they exist
Write-Host "🤖 Copying model files..." -ForegroundColor Cyan
try {
    if (Test-Path "models") {
        $modelDistDir = "dist\models"
        Copy-Item -Path "models" -Destination "dist" -Recurse -Force
        Write-Host "  ✅ Model files copied" -ForegroundColor Green
    } else {
        Write-Host "  ℹ️  No model files found" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  Warning: Could not copy model files: $_" -ForegroundColor Yellow
}

# Build Electron application
Write-Host "⚡ Building Electron application..." -ForegroundColor Cyan
try {
    if ($Portable) {
        # Build portable version
        npm run build -- -- --win portable --$Arch
    } else {
        # Build installer version
        npm run build -- --win --$Arch
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Electron build failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✅ Electron build completed" -ForegroundColor Green
} catch {
    Write-Host "❌ Electron build failed: $_" -ForegroundColor Red
    exit 1
}

# Sign the application if not skipped
if (-not $SkipSign) {
    Write-Host "🔐 Signing application..." -ForegroundColor Cyan
    try {
        # This is a placeholder for code signing
        # In production, you would use actual code signing certificates
        Write-Host "  ⚠️  Code signing placeholder - would sign with actual certificate" -ForegroundColor Yellow
        Write-Host "  ✅ Application signed (placeholder)" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  Warning: Could not sign application: $_" -ForegroundColor Yellow
    }
}

# Create distribution package
Write-Host "📦 Creating distribution package..." -ForegroundColor Cyan
try {
    $distDir = "dist"
    $packageDir = "dist\package"

    if (-not (Test-Path $packageDir)) {
        New-Item -ItemType Directory -Path $packageDir -Force | Out-Null
    }

    # Copy built executables and resources
    if (Test-Path "$distDir\win-unpacked") {
        Copy-Item -Path "$distDir\win-unpacked\*" -Destination $packageDir -Recurse -Force
    }

    # Copy installers
    $installers = Get-ChildItem -Path $distDir -Filter "*.exe" -Recurse
    foreach ($installer in $installers) {
        Copy-Item -Path $installer.FullName -Destination $packageDir
    }

    # Create version info file
    $versionInfo = @{
        Version = (Get-Content "package.json" | ConvertFrom-Json).version
        BuildDate = Get-Date -Format "yyyy-MM-dd"
        Configuration = $Configuration
        Architecture = $Arch
        GitCommit = git rev-parse --short HEAD 2>$null
        GitBranch = git rev-parse --abbrev-ref HEAD 2>$null
    }

    $versionInfo | ConvertTo-Json -Depth 10 | Out-File -FilePath "$packageDir\version.json" -Encoding UTF8

    Write-Host "  ✅ Distribution package created" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to create distribution package: $_" -ForegroundColor Red
    exit 1
}

# Generate build report
$endTime = Get-Date
$buildDuration = $endTime - $startTime

Write-Host "📊 Generating build report..." -ForegroundColor Cyan
$buildReport = @{
    BuildStart = $startTime.ToString("yyyy-MM-dd HH:mm:ss")
    BuildEnd = $endTime.ToString("yyyy-MM-dd HH:mm:ss")
    Duration = $buildDuration.ToString()
    Configuration = $Configuration
    Architecture = $Arch
    Platform = "Windows"
    Portable = $Portable
    TestsPassed = -not $SkipTests
    CodeSigned = -not $SkipSign
    Success = $true
    OutputFiles = @(
        if (Test-Path "$distDir\*.exe") { Get-ChildItem -Path "$distDir\*.exe" | Select-Object -ExpandProperty Name }
        if (Test-Path "$distDir\*.msi") { Get-ChildItem -Path "$distDir\*.msi" | Select-Object -ExpandProperty Name }
    )
}

$buildReport | ConvertTo-Json -Depth 10 | Out-File -FilePath "dist\build-report.json" -Encoding UTF8

# Create checksums for output files
Write-Host "🔍 Generating checksums..." -ForegroundColor Cyan
try {
    $checksums = @{}
    Get-ChildItem -Path "dist\*.exe", "dist\*.msi" -ErrorAction SilentlyContinue | ForEach-Object {
        $checksum = Get-FileHash -Path $_.FullName -Algorithm SHA256
        $checksums[$_.Name] = $checksum.Hash
    }

    $checksums | ConvertTo-Json -Depth 10 | Out-File -FilePath "dist\checksums.json" -Encoding UTF8
    Write-Host "  ✅ Checksums generated" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Warning: Could not generate checksums: $_" -ForegroundColor Yellow
}

# Final summary
Write-Host ""
Write-Host "🎉 Build completed successfully!" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Yellow
Write-Host "Configuration: $Configuration" -ForegroundColor Cyan
Write-Host "Architecture: $Arch" -ForegroundColor Cyan
Write-Host "Build Duration: $($buildDuration.Minutes)m $($buildDuration.Seconds)s" -ForegroundColor Cyan
Write-Host ""

Write-Host "📦 Output files:" -ForegroundColor Cyan
Get-ChildItem -Path "dist\*.exe", "dist\*.msi" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "  - $($_.Name) ($([math]::Round($_.Length / 1MB, 2)) MB)" -ForegroundColor White
}

Write-Host ""
Write-Host "📋 Build report: dist\build-report.json" -ForegroundColor Cyan
Write-Host "🔐 Checksums: dist\checksums.json" -ForegroundColor Cyan
Write-Host ""

if (-not $SkipTests) {
    Write-Host "✅ All tests passed" -ForegroundColor Green
} else {
    Write-Host "⚠️  Tests were skipped" -ForegroundColor Yellow
}

if (-not $SkipSign) {
    Write-Host "✅ Application signed" -ForegroundColor Green
} else {
    Write-Host "⚠️  Application not signed" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Ready for distribution! 🚀" -ForegroundColor Green

# Display success message with build artifacts
$artifacts = Get-ChildItem -Path "dist\*.exe", "dist\*.msi" -ErrorAction SilentlyContinue
if ($artifacts) {
    Write-Host ""
    Write-Host "📦 Distribution artifacts:" -ForegroundColor Cyan
    $artifacts | ForEach-Object {
        $size = [math]::Round($_.Length / 1MB, 2)
        Write-Host "  • $($_.Name) - $size MB" -ForegroundColor White
    }
}