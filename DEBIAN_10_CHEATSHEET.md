# 📋 Шпаргалка для Debian 10 (Python 3.7.3)

## Быстрый старт

### 1. Подготовка системы

```bash
# Обновление пакетов
sudo apt update && sudo apt upgrade -y

# Установка системных зависимостей
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev
```

### 2. Установка приложения

```bash
# Переход в директорию
cd /opt/jira_report

# Создание виртуального окружения
python3 -m venv venv

# Активация
source venv/bin/activate

# Обновление pip
pip install --upgrade pip==23.3.1

# Установка зависимостей
pip install -r requirements.txt
```

### 3. Настройка

```bash
# Копирование конфига
cp configs/.env.example .env

# Редактирование .env
nano .env

# Инициализация БД
python scripts/init_db.py
```

### 4. Запуск

```bash
# Development режим
python app.py

# Production (через gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 web.app:app
```

---

## Установка как службу (systemd)

### 1. Создание службы

```bash
sudo nano /etc/systemd/system/jira-report.service
```

Содержимое:
```ini
[Unit]
Description=Jira Report System
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/jira_report
Environment="PATH=/opt/jira_report/venv/bin"
ExecStart=/opt/jira_report/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### 2. Запуск службы

```bash
# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозагрузки
sudo systemctl enable jira-report

# Запуск
sudo systemctl start jira-report

# Проверка статуса
sudo systemctl status jira-report
```

### 3. Логи

```bash
# Просмотр логов
journalctl -u jira-report -f

# Логи за сегодня
journalctl -u jira-report --since today
```

---

## Настройка Telegram бота

### 1. Создание бота

1. Открыть @BotFather в Telegram
2. Отправить `/newbot`
3. Ввести имя: `Jira Report Bot`
4. Ввести username: `jira_report_bot`
5. Скопировать токен

### 2. Настройка

```bash
nano .env
```

Добавить:
```ini
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### 3. Перезапуск

```bash
sudo systemctl restart jira-report
```

### 4. Тестирование

1. Найти бота по username
2. Отправить `/start`
3. Бот должен ответить приветствием

---

## Настройка Email (Gmail)

### 1. Создание App Password

1. Включить 2FA: https://myaccount.google.com/security
2. Создать App Password: https://myaccount.google.com/apppasswords
3. Скопировать 16-значный пароль

### 2. Настройка

```bash
nano .env
```

Добавить:
```ini
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=16-digit-app-password
EMAIL_FROM=Jira Report <your-email@gmail.com>
```

### 3. Перезапуск

```bash
sudo systemctl restart jira-report
```

---

## Управление приложением

### Перезапуск

```bash
sudo systemctl restart jira-report
```

### Остановка

```bash
sudo systemctl stop jira-report
```

### Старт

```bash
sudo systemctl start jira-report
```

### Проверка статуса

```bash
sudo systemctl status jira-report
```

### Просмотр логов

```bash
journalctl -u jira-report -f
```

---

## Обновление приложения

```bash
# Переход в директорию
cd /opt/jira_report

# Активация venv
source venv/bin/activate

# Pull изменений из git
git pull origin main

# Установка новых зависимостей
pip install -r requirements.txt

# Инициализация БД (если были изменения в моделях)
python scripts/init_db.py

# Перезапуск службы
sudo systemctl restart jira-report
```

---

## Резервное копирование

### База данных

```bash
# Копирование БД
cp /opt/jira_report/jira_report.db /backup/jira_report_$(date +%Y%m%d).db

# Восстановление
cp /backup/jira_report_20240308.db /opt/jira_report/jira_report.db
```

### Конфигурация

```bash
# Копирование .env
cp /opt/jira_report/.env /backup/jira_report_env_$(date +%Y%m%d)
```

---

## Troubleshooting

### Ошибка: ModuleNotFoundError

```bash
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart jira-report
```

### Ошибка: Database is locked

```bash
# Остановка приложения
sudo systemctl stop jira-report

# Проверка процессов
lsof /opt/jira_report/jira_report.db

# Удаление lock файла (если есть)
rm -f /opt/jira_report/jira_report.db-shm
rm -f /opt/jira_report/jira_report.db-wal

# Запуск
sudo systemctl start jira-report
```

### Ошибка: WeasyPrint не работает

```bash
# Проверка установленных библиотек
dpkg -l | grep pango
dpkg -l | grep gdk-pixbuf

# Переустановка
sudo apt install --reinstall \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info

pip install --force-reinstall weasyprint==52.5
sudo systemctl restart jira-report
```

### Ошибка: Порт 5000 занят

```bash
# Проверка порта
sudo netstat -tlnp | grep 5000

# Изменение порта в .env
nano .env
# PROD_PORT=5001

sudo systemctl restart jira-report
```

---

## Проверка работы

### Health check

```bash
curl http://localhost:5000/health
```

### API тест

```bash
curl http://localhost:5000/api/reports/history
```

### Проверка версии Python

```bash
source venv/bin/activate
python --version  # Должно быть Python 3.7.3
```

### Проверка пакетов

```bash
source venv/bin/activate
pip list | grep -E "Flask|SQLAlchemy|telegram|APScheduler|weasyprint"
```

---

## Полезные команды

### Очистка кэша pip

```bash
pip cache purge
```

### Проверка места на диске

```bash
df -h
du -sh /opt/jira_report/*
```

### Проверка логов на ошибки

```bash
journalctl -u jira-report | grep -i error
```

### Мониторинг процессов

```bash
top -u www-data
ps aux | grep python
```

---

## Контакты

По вопросам администрирования обращайтесь к системному администратору.
