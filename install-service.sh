#!/bin/bash
# =============================================
# Скрипт установки службы Jira Report Web
# Запускать от root через sudo
# =============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="jira-report"

echo "🔧 Установка службы $SERVICE_NAME..."

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Запустите скрипт через sudo:"
    echo "   sudo ./install-service.sh"
    exit 1
fi

# Проверка .env
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "⚠️  Файл .env не найден!"
    echo "   Создайте .env перед установкой службы:"
    echo "   cp .env.example .env"
    exit 1
fi

# Копирование файла службы
cp "$SCRIPT_DIR/${SERVICE_NAME}.service" "/etc/systemd/system/${SERVICE_NAME}.service"

echo "✅ Файл службы скопирован"

# Перезагрузка systemd
systemctl daemon-reload

# Включение и запуск службы
systemctl enable ${SERVICE_NAME}.service
systemctl start ${SERVICE_NAME}.service

echo "✅ Служба установлена и запущена"
echo ""
echo "📊 Статус службы:"
systemctl status ${SERVICE_NAME}.service --no-pager
echo ""
echo "📝 Просмотр логов:"
echo "   journalctl -u ${SERVICE_NAME}.service -f"
echo ""
echo "🔧 Управление службой:"
echo "   sudo systemctl start ${SERVICE_NAME}.service     # Запустить"
echo "   sudo systemctl stop ${SERVICE_NAME}.service      # Остановить"
echo "   sudo systemctl restart ${SERVICE_NAME}.service   # Перезапустить"
echo "   sudo systemctl disable ${SERVICE_NAME}.service   # Отключить"
