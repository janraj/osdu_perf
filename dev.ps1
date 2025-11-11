# OSDU Performance Testing - Development Scripts
# PowerShell script for Windows development tasks

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("test", "test-unit", "test-cov", "install", "clean", "lint", "format", "help")]
    [string]$Command
)

function Show-Help {
    Write-Host "OSDU Performance Testing - Development Commands" -ForegroundColor Green
    Write-Host "Usage: .\dev.ps1 <command>" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Available commands:" -ForegroundColor Cyan
    Write-Host "  test        - Run all unit tests"
    Write-Host "  test-unit   - Run unit tests (same as test)"
    Write-Host "  test-cov    - Run tests with coverage report"
    Write-Host "  install     - Install package in development mode"
    Write-Host "  clean       - Clean up generated files"
    Write-Host "  lint        - Run code linting"
    Write-Host "  format      - Format code with black"
    Write-Host "  help        - Show this help message"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\dev.ps1 test"
    Write-Host "  .\dev.ps1 test-cov"
    Write-Host "  .\dev.ps1 clean"
}

function Run-Tests {
    Write-Host "Running unit tests..." -ForegroundColor Green
    python -m pytest tests/unit/
}

function Run-TestsWithCoverage {
    Write-Host "Running tests with coverage..." -ForegroundColor Green
    python -m pytest tests/unit/ --cov=osdu_perf --cov-report=html --cov-report=term-missing
}

function Install-Package {
    Write-Host "Installing package in development mode..." -ForegroundColor Green
    pip install -e .
}

function Clean-Files {
    Write-Host "Cleaning up generated files..." -ForegroundColor Green
    
    # Remove __pycache__ directories
    Get-ChildItem -Path . -Recurse -Directory -Name "__pycache__" | ForEach-Object {
        $path = $_.FullName
        if (Test-Path $path) {
            Remove-Item -Path $path -Recurse -Force
            Write-Host "Removed: $path" -ForegroundColor Yellow
        }
    }
    
    # Remove .pyc files
    Get-ChildItem -Path . -Recurse -File -Name "*.pyc" | ForEach-Object {
        Remove-Item -Path $_.FullName -Force
    }
    
    # Remove test and coverage artifacts
    $artifacts = @(".pytest_cache", "htmlcov", ".coverage", "osdu_perf.egg-info")
    foreach ($artifact in $artifacts) {
        if (Test-Path $artifact) {
            Remove-Item -Path $artifact -Recurse -Force
            Write-Host "Removed: $artifact" -ForegroundColor Yellow
        }
    }
    
    Write-Host "Cleanup complete." -ForegroundColor Green
}

function Run-Linting {
    Write-Host "Running code linting..." -ForegroundColor Green
    flake8 osdu_perf tests
}

function Format-Code {
    Write-Host "Formatting code with black..." -ForegroundColor Green
    black osdu_perf tests
}

# Execute the requested command
switch ($Command) {
    "test" { Run-Tests }
    "test-unit" { Run-Tests }
    "test-cov" { Run-TestsWithCoverage }
    "install" { Install-Package }
    "clean" { Clean-Files }
    "lint" { Run-Linting }
    "format" { Format-Code }
    "help" { Show-Help }
}