# =============================================
# JIRA REPORT SYSTEM — БЭКАП КОНФИГУРАЦИИ
# =============================================
# Скрипт создаёт резервную копию .env файла
# Хранит последние 10 бэкапов

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$envFile = Join-Path $projectRoot ".env"
$backupDir = Join-Path $projectRoot "backups"

# Создаём директорию для бэкапов
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
    Write-Host "Создана директория для бэкапов: $backupDir"
}

# Проверяем существование .env
if (-not (Test-Path $envFile)) {
    Write-Error "Файл .env не найден: $envFile"
    exit 1
}

# Создаём имя файла с датой
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $backupDir ".env.$timestamp"

# Копируем файл
Copy-Item $envFile $backupFile
Write-Host "✓ Бэкап создан: $backupFile"

# Удаляем старые бэкапы (храним последние 10)
$backups = Get-ChildItem $backupDir -Filter ".env.*" | Sort-Object LastWriteTime -Descending
if ($backups.Count -gt 10) {
    $oldBackups = $backups | Select-Object -Skip 10
    foreach ($backup in $oldBackups) {
        Remove-Item $backup.FullName
        Write-Host "✓ Удалён старый бэкап: $($backup.Name)"
    }
}

Write-Host "`nБэкапирование завершено!"
Write-Host "Всего бэкапов: $($backups.Count)"
