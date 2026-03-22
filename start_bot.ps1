# start_bot.ps1 — Run the Telegram bot
# Double-click this file or run it in PowerShell

$env:TELEGRAM_BOT_TOKEN = "YOUR_TOKEN_HERE"
$env:OLLAMA_KEEP_ALIVE  = "30m"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
$env:OLLAMA_NUM_PARALLEL = "1"

Write-Host "Starting AI Dev Engine Telegram Bot..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop.`n" -ForegroundColor Yellow

py telegram_bot.py
