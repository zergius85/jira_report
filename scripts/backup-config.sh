#!/bin/bash
# =============================================
# JIRA REPORT SYSTEM — БЭКАП КОНФИГУРАЦИИ
# =============================================
# Скрипт создаёт резервную копию .env файла
# Хранит последние 10 бэкапов в папке backups/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"
BACKUP_DIR="$SCRIPT_DIR/backups"

# Создаём директорию для бэкапов
if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
    echo "✓ Создана директория для бэкапов: $BACKUP_DIR"
fi

# Проверяем существование .env
if [ ! -f "$ENV_FILE" ]; then
    echo "✗ Ошибка: Файл .env не найден: $ENV_FILE"
    exit 1
fi

# Создаём имя файла с датой
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/.env.$TIMESTAMP"

# Копируем файл
cp "$ENV_FILE" "$BACKUP_FILE"
echo "✓ Бэкап создан: $BACKUP_FILE"

# Удаляем старые бэкапы (храним последние 10)
cd "$BACKUP_DIR" || exit 1
BACKUP_COUNT=$(ls -1 .env.* 2>/dev/null | wc -l)

if [ "$BACKUP_COUNT" -gt 10 ]; then
    ls -1t .env.* | tail -n +11 | xargs -r rm
    echo "✓ Удалены старые бэкапы"
fi

echo ""
echo "Бэкапирование завершено!"
echo "Всего бэкапов: $(ls -1 .env.* 2>/dev/null | wc -l)"
