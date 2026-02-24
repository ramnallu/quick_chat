# scripts/run_streamlit.ps1
# Activate .venv if not active (create + install requirements if needed), then run Streamlit app
Param(
    [string]$VenvPath = ".\.venv",
    [string]$AppPath = "app/streamlit_app.py"
)

Write-Host "Run Streamlit (PowerShell helper)"

if (-not $env:VIRTUAL_ENV) {
    $activate = Join-Path $VenvPath "Scripts\Activate.ps1"
    if (Test-Path $activate) {
        Write-Host "Activating virtualenv at $VenvPath"
        . $activate
    } else {
        Write-Host "Virtualenv not found at $VenvPath. Creating..."
        python -m venv $VenvPath
        if (Test-Path $activate) {
            . $activate
            if (Test-Path "requirements.txt") {
                Write-Host "Installing requirements from requirements.txt..."
                pip install -r requirements.txt
            }
        } else {
            Write-Error "Failed to create or locate activate script at $activate"
            exit 1
        }
    }
} else {
    Write-Host "Virtualenv already active."
}

Write-Host "Starting Streamlit app: $AppPath"
streamlit run $AppPath
