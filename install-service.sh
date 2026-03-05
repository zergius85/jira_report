#!/bin/bash
# =============================================
# Скрипт установки службы Jira Report Web
# Запускать от root через sudo
# =============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="jira-report"
SERVICE_FILE="${SERVICE_NAME}.service"
SYSTEMD_DIR="/etc/systemd/system"
ENV_FILE="$SCRIPT_DIR/.env"
CONFIG_FILE="$SCRIPT_DIR/config.py"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Режим по умолчанию (можно переключить флагом)
MODE=""

# =============================================
# Парсинг аргументов
# =============================================
while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            MODE="development"
            shift
            ;;
        --prod|--production)
            MODE="production"
            shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Неизвестный параметр: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# =============================================
# Функция показа справки
# =============================================
show_help() {
    echo "Использование: $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  --dev          Установить в режиме разработки (dev)"
    echo "  --prod         Установить в режиме production (по умолчанию)"
    echo "  --uninstall    Удалить службу"
    echo "  --help, -h     Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  sudo $0 --dev     # Установить dev версию"
    echo "  sudo $0 --prod    # Установить production версию"
    echo "  sudo $0 --uninstall  # Удалить службу"
}

# =============================================
# Проверка: если режим не указан — показываем help
# =============================================
if [ "$UNINSTALL" != true ] && [ -z "$MODE" ]; then
    echo -e "${YELLOW}⚠️  Не указан режим установки!${NC}"
    echo ""
    show_help
    exit 1
fi

# =============================================
# Функция uninstall
# =============================================
do_uninstall() {
    echo -e "${YELLOW}🔧 Удаление службы $SERVICE_NAME...${NC}"
    
    # Проверка прав root
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}❌ Запустите скрипт через sudo:${NC}"
        echo "   sudo $0 --uninstall"
        exit 1
    fi
    
    # Остановка службы
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "⏹️  Остановка службы..."
        systemctl stop $SERVICE_NAME
    fi
    
    # Отключение службы
    if systemctl is-enabled --quiet $SERVICE_NAME 2>/dev/null; then
        echo "⏹️  Отключение службы из автозагрузки..."
        systemctl disable $SERVICE_NAME
    fi
    
    # Удаление файла службы
    if [ -f "$SYSTEMD_DIR/${SERVICE_NAME}.service" ]; then
        echo "🗑️  Удаление файла службы..."
        rm -f "$SYSTEMD_DIR/${SERVICE_NAME}.service"
    fi
    
    # Перезагрузка systemd
    systemctl daemon-reload
    
    echo -e "${GREEN}✅ Служба $SERVICE_NAME удалена!${NC}"
    echo ""
    echo "📝 Файлы конфигурации и .env сохранены."
    echo "   При необходимости удалите их вручную:"
    echo "   rm -rf $SCRIPT_DIR"
    exit 0
}

# =============================================
# Выполнение uninstall если запрошено
# =============================================
if [ "$UNINSTALL" = true ]; then
    do_uninstall
fi

# =============================================
# Установка службы
# =============================================
echo -e "${BLUE}🔧 Установка службы $SERVICE_NAME (режим: $MODE)...${NC}"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Запустите скрипт через sudo:${NC}"
    echo "   sudo $0 --$MODE"
    exit 1
fi

# Проверка .env
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚠️  Файл .env не найден!${NC}"
    echo "   Создайте .env перед установкой службы:"
    echo "   cp .env.example .env"
    exit 1
fi

# Проверка config.py
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Файл config.py не найден!${NC}"
    echo "   Убедитесь, что config.py существует в директории службы"
    exit 1
fi

# Проверка systemd
if ! command -v systemctl &> /dev/null; then
    echo -e "${RED}❌ systemd не найден!${NC}"
    echo "   Этот скрипт требует systemd для установки службы"
    exit 1
fi

# Создание резервной копии существующей службы если есть
if [ -f "$SYSTEMD_DIR/${SERVICE_NAME}.service" ]; then
    echo -e "${YELLOW}⚠️  Служба уже существует, создаю резервную копию...${NC}"
    cp "$SYSTEMD_DIR/${SERVICE_NAME}.service" "$SYSTEMD_DIR/${SERVICE_NAME}.service.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Обновление файла службы с правильным режимом
echo "📝 Настройка файла службы (режим: $MODE)..."

# Создаём временный файл службы с правильным режимом
TEMP_SERVICE=$(mktemp)
cp "$SCRIPT_DIR/${SERVICE_FILE}.template" "$TEMP_SERVICE" 2>/dev/null || cp "$SCRIPT_DIR/${SERVICE_FILE}" "$TEMP_SERVICE"

# Заменяем FLASK_ENV в файле службы
sed -i "s/FLASK_ENV=development/FLASK_ENV=$MODE/g" "$TEMP_SERVICE"

# Копирование файла службы
echo "📋 Копирование файла службы в $SYSTEMD_DIR..."
cp "$TEMP_SERVICE" "$SYSTEMD_DIR/${SERVICE_NAME}.service"
rm -f "$TEMP_SERVICE"

echo -e "${GREEN}✅ Файл службы скопирован${NC}"

# Перезагрузка systemd
echo "🔄 Перезагрузка systemd..."
systemctl daemon-reload

# Включение и запуск службы
echo "🔌 Включение службы в автозагрузку..."
systemctl enable ${SERVICE_NAME}.service

echo "🚀 Запуск службы..."
systemctl start ${SERVICE_NAME}.service

# Пауза для запуска службы
sleep 2

echo ""
echo -e "${GREEN}✅ Служба установлена и запущена!${NC}"
echo ""
echo "📊 Статус службы:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
systemctl status ${SERVICE_NAME}.service --no-pager
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${BLUE}📝 Полезные команды:${NC}"
echo "   journalctl -u ${SERVICE_NAME}.service -f     # Просмотр логов в реальном времени"
echo "   journalctl -u ${SERVICE_NAME}.service --since today  # Логи за сегодня"
echo ""
echo -e "${BLUE}🔧 Управление службой:${NC}"
echo "   sudo systemctl start ${SERVICE_NAME}.service     # Запустить"
echo "   sudo systemctl stop ${SERVICE_NAME}.service      # Остановить"
echo "   sudo systemctl restart ${SERVICE_NAME}.service   # Перезапустить"
echo "   sudo systemctl disable ${SERVICE_NAME}.service   # Отключить"
echo "   sudo $0 --uninstall                              # Удалить службу"
echo ""
echo -e "${BLUE}🌐 Доступ к веб-интерфейсу:${NC}"
if [ "$MODE" = "production" ]; then
    echo "   Production режим: http://<server-ip>:5000"
else
    echo "   Development режим: http://<server-ip>:5001"
fi
echo ""
echo -e "${YELLOW}⚠️  Не забудьте проверить файл .env и настройки брандмауэра!${NC}"
