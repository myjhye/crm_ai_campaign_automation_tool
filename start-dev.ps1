[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$Port = 8000,
    [switch]$SkipDatabase,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$browserJob = $null
$exitCode = 0
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        throw 'Missing .venv. Follow the installation steps in README.md first.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env'))) {
        throw 'Missing .env. Copy .env.example and configure your database first.'
    }

    # Fail before starting a browser if another process already owns this port.
    $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    try { $probe.Start() }
    catch { throw "Port $Port is already in use. Stop the existing server or pass -Port 8001." }
    finally { $probe.Stop() }

    if (-not $SkipDatabase) {
        Write-Host 'Starting PostgreSQL (Docker Desktop must be running)...'
        & docker compose up -d --wait db
        if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed. Check Docker Desktop and .env.' }
    }
    Write-Host 'Applying database migrations...'
    & $pythonPath -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed. Check DATABASE_URL and database availability.' }

    $appUrl = "http://127.0.0.1:$Port/"
    if (-not $NoBrowser) {
        # Wait for this foreground server to serve HTML, then open the default browser once.
        $browserJob = Start-Job -ArgumentList $appUrl -ScriptBlock {
            param($url)
            for ($attempt = 0; $attempt -lt 60; $attempt++) {
                try {
                    $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
                    if ($response.StatusCode -eq 200 -and $response.Content -match 'GrowthPilot') {
                        Start-Process -FilePath $url
                        return
                    }
                } catch { }
                Start-Sleep -Milliseconds 500
            }
            Write-Warning "Browser launch timed out. Open $url manually after checking the server log."
        }
    }
    Write-Host "GrowthPilot: $appUrl"
    Write-Host 'Press Ctrl+C in this terminal to stop the API. PostgreSQL remains running.'
    & $pythonPath -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port
    $exitCode = $LASTEXITCODE
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    $exitCode = 1
} finally {
    if ($null -ne $browserJob) {
        Stop-Job -Job $browserJob -ErrorAction SilentlyContinue
        Receive-Job -Job $browserJob -ErrorAction SilentlyContinue
        Remove-Job -Job $browserJob -Force -ErrorAction SilentlyContinue
    }
    Pop-Location
}
exit $exitCode
