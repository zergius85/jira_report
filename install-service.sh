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
        --from-env)
            FROM_ENV=true
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
    echo "  --from-env     Использовать .env.preinstall (неинтерактивный режим)"
    echo "  --help, -h     Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  sudo $0 --dev                    # Интерактивная установка dev версии"
    echo "  sudo $0 --prod                   # Интерактивная установка production версии"
    echo "  sudo $0 --from-env --prod        # Неинтерактивная установка из .env.preinstall"
    echo "  sudo $0 --uninstall              # Удалить службу"
}

# =============================================
# Функция создания .env
# =============================================
create_env_file() {
    local env_file="$SCRIPT_DIR/.env"
    
    # Если .env уже существует — спрашиваем要不要 перезаписать
    if [ -f "$env_file" ]; then
        echo -e "${YELLOW}⚠️  Файл .env уже существует!${NC}"
        read -p "🔄 Перезаписать? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "✅ Пропущено, используем существующий .env"
            return 0
        fi
    fi
    
    echo -e "${BLUE}📝 Создание файла .env...${NC}"
    echo ""
    echo "Заполните параметры подключения к Jira:"
    echo "   (нажмите Enter для использования значения по умолчанию)"
    echo ""
    
    # JIRA_SERVER
    read -p "JIRA_SERVER (например, https://jira.company.com): " -r jira_server
    if [ -z "$jira_server" ]; then
        jira_server="https://jira.example.com"
    fi
    
    # JIRA_USER
    read -p "JIRA_USER (email или username): " -r jira_user
    if [ -z "$jira_user" ]; then
        jira_user="user@example.com"
    fi
    
    # JIRA_PASS (скрытый ввод)
    read -s -p "JIRA_PASS (пароль или API token): " -r jira_pass
    echo
    if [ -z "$jira_pass" ]; then
        echo -e "${RED}❌ Пароль не может быть пустым!${NC}"
        exit 1
    fi
    
    # EXCLUDED_PROJECTS
    read -p "EXCLUDED_PROJECTS (через запятую, например TEST,DEMO): " -r excluded_projects
    if [ -z "$excluded_projects" ]; then
        excluded_projects="TEST,SANDBOX"
    fi
    
    # INTERNAL_PROJECTS
    read -p "INTERNAL_PROJECTS (для вкладки 'Непонятное', например NEW,local): " -r internal_projects
    if [ -z "$internal_projects" ]; then
        internal_projects="NEW,local"
    fi
    
    # EXCLUDED_ASSIGNEE_CLOSE
    read -p "EXCLUDED_ASSIGNEE_CLOSE (исключения для статуса Закрыт, например holin,admin): " -r excluded_assignees
    if [ -z "$excluded_assignees" ]; then
        excluded_assignees="holin,admin"
    fi
    
    # SSL_VERIFY
    echo ""
    echo "Проверка SSL:"
    echo "  y - Включена (рекомендуется для продакшена)"
    echo "  n - Отключена (для внутренних серверов с self-signed сертификатами)"
    read -p "SSL_VERIFY (y/n): " -r ssl_verify
    if [[ $ssl_verify =~ ^[Nn]$ ]]; then
        ssl_verify="false"
    else
        ssl_verify="true"
    fi
    
    # FLASK_ENV
    echo ""
    echo "Режим работы:"
    echo "  1 - Development (порт 5001, отладка включена)"
    echo "  2 - Production (порт 5000, отладка отключена)"
    read -p "Выберите режим (1/2): " -r flask_mode
    if [[ $flask_mode =~ ^1$ ]]; then
        flask_env="development"
    else
        flask_env="production"
    fi
    
    # Создаём файл .env
    cat > "$env_file" <<EOF
# =============================================
# JIRA REPORT SYSTEM — КОНФИГУРАЦИЯ
# =============================================
# Сгенерировано скриптом install-service.sh $(date +%Y-%m-%d)

# --- ПОДКЛЮЧЕНИЕ К JIRA (ОБЯЗАТЕЛЬНО) ---
JIRA_SERVER=$jira_server
JIRA_USER=$jira_user
JIRA_PASS=$jira_pass

# --- НАСТРОЙКИ ОТЧЁТОВ ---
# Проекты для исключения из отчётов (через запятую, без пробелов)
EXCLUDED_PROJECTS=$excluded_projects

# Внутренние проекты для вкладки "Непонятное" (через запятую)
INTERNAL_PROJECTS=$internal_projects

# ID статусов "Закрыт"/"Closed" (автоматически определяется при первом запуске)
# Оставьте пустым для авто-определения
CLOSED_STATUS_IDS=

# Пользователи, для которых статус "Закрыт" не считается ошибкой (через запятую)
EXCLUDED_ASSIGNEE_CLOSE=$excluded_assignees

# --- БЕЗОПАСНОСТЬ ---
# Отключить проверку SSL (true/false) — только для внутренних серверов
SSL_VERIFY=$ssl_verify

# =============================================
# РЕЖИМ РАБОТЫ (НЕ МЕНЯТЬ БЕЗ НУЖДЫ)
# =============================================
# FLASK_ENV=production — для продакшена (порт 5000)
# FLASK_ENV=development — для разработки (порт 5001, по умолчанию)
FLASK_ENV=$flask_env

# Логирование: DEBUG (dev) или INFO (prod)
LOG_LEVEL=$( [ "$flask_env" = "production" ] && echo "INFO" || echo "DEBUG" )
EOF

    # Устанавливаем правильные права на файл (только владелец может читать)
    chmod 600 "$env_file"
    
    echo -e "${GREEN}✅ Файл .env создан!${NC}"
    echo "   Путь: $env_file"
    echo ""
    echo -e "${YELLOW}⚠️  Важно: файл .env содержит пароли!${NC}"
    echo "   Убедитесь, что права установлены корректно (chmod 600)"
    echo ""
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
# Создание .env если не существует
# =============================================
if [ ! -f "$ENV_FILE" ]; then
    # Проверяем, есть ли .env.preinstall и флаг --from-env
    if [ "$FROM_ENV" = true ] && [ -f "$SCRIPT_DIR/.env.preinstall" ]; then
        echo -e "${BLUE}📋 Копирование .env из .env.preinstall...${NC}"
        cp "$SCRIPT_DIR/.env.preinstall" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        echo -e "${GREEN}✅ .env создан из .env.preinstall!${NC}"
        echo ""
        echo -e "${YELLOW}⚠️  Не забудьте проверить и заполнить CLOSED_STATUS_IDS!${NC}"
    elif [ "$FROM_ENV" = true ]; then
        echo -e "${RED}❌ Файл .env.preinstall не найден!${NC}"
        echo "   Создайте .env.preinstall или запустите без --from-env"
        exit 1
    else
        echo -e "${YELLOW}⚠️  Файл .env не найден!${NC}"
        echo ""
        read -p "📝 Хотите создать .env сейчас? (y/N): " -r create_env
        echo
        if [[ $create_env =~ ^[Yy]$ ]]; then
            create_env_file
        else
            echo -e "${RED}❌ Установка невозможна без .env!${NC}"
            echo "   Создайте .env вручную или запустите скрипт снова"
            exit 1
        fi
    fi
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
