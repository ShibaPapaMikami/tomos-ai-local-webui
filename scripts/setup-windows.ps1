$ErrorActionPreference = "Stop"

$Model = if ($env:GEMMA_MODEL) { $env:GEMMA_MODEL } else { "gemma4:12b" }
$CodingModel = if ($env:GEMMA_CODING_MODEL) { $env:GEMMA_CODING_MODEL } else { "" }

Write-Host "Gemma 4 local Web UI - Windows setup"
Write-Host ""

function Test-Command($Name) {
  return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command "python")) {
  Write-Host "Python が見つかりません。"
  Write-Host "https://www.python.org/downloads/ から Python 3 をインストールし、'Add python.exe to PATH' を有効にしてください。"
  exit 1
}

python --version

python -c "import segno" 2>$null
if ($LASTEXITCODE -ne 0) {
  python -m pip install --user segno
}

if (-not (Test-Command "ollama")) {
  Write-Host "Ollama が見つかりません。"
  Write-Host "https://ollama.com/download から Ollama をインストールしてから、もう一度このスクリプトを実行してください。"
  exit 1
}

ollama --version

try {
  Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 2 | Out-Null
} catch {
  Write-Host "Ollama サーバーを起動します..."
  Start-Process -WindowStyle Minimized -FilePath "ollama" -ArgumentList "serve"
  Start-Sleep -Seconds 3
}

try {
  Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 5 | Out-Null
} catch {
  Write-Host "Ollama を起動できませんでした。Ollama アプリを開いてから再実行してください。"
  exit 1
}

$InstalledModels = ollama list | Select-String -Pattern "^$Model\s"
if (-not $InstalledModels) {
  Write-Host "$Model をダウンロードします。初回は数GBの通信が発生します。"
  ollama pull $Model
} else {
  Write-Host "Model: installed ($Model)"
}

if ($CodingModel -and $CodingModel -ne $Model) {
  $InstalledCodingModels = ollama list | Select-String -Pattern "^$([regex]::Escape($CodingModel))\s"
  if (-not $InstalledCodingModels) {
    Write-Host "$CodingModel をコード生成用にダウンロードします。"
    ollama pull $CodingModel
  } else {
    Write-Host "Coding model: installed ($CodingModel)"
  }
}

Write-Host ""
Write-Host "準備完了です。次は Gemma4_12B_Web.bat をダブルクリックしてください。"
