# =============================================
# ТРЕБОВАНИЯ К СРЕДЕ ВЫПОЛНЕНИЯ
# =============================================
# Этот файл фиксирует требования к окружению
# для развёртывания Jira Report System
# =============================================

## Операционная система
- **OS:** Debian 10 (buster) или совместимая
- **Архитектура:** x86_64 (amd64)

## Python
- **Минимальная версия:** Python 3.7.3
- **Максимальная версия:** Python 3.11.x (проверено)
- **Не рекомендуется:** Python 3.12+ (требуется тестирование)

### Для Debian 10 (buster)
```bash
# Python 3.7.3 установлен по умолчанию
python3 --version  # Должно быть: Python 3.7.3

# Установка pip
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Обновление pip
pip install --upgrade pip==23.3.1
```

## Системные зависимости (Debian 10)

### Для WeasyPrint (PDF экспорт)
```bash
sudo apt install -y \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info
```

### Для компиляции C-расширений
```bash
sudo apt install -y \
    build-essential \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev
```

## Переменные окружения

### Обязательные
```bash
# Jira
JIRA_SERVER=https://your-jira-server.com
JIRA_USER=your.email@company.com
JIRA_PASS=your_password_or_token

# База данных
DATABASE_URL=sqlite:///jira_report.db
```

### Опциональные
```bash
# Telegram (для уведомлений)
TELEGRAM_BOT_TOKEN=bot-token-here

# Email (SMTP для отправки отчётов)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
EMAIL_FROM=Jira Report <noreply@jira-report.local>

# Режим работы
FLASK_ENV=development  # или production
LOG_LEVEL=INFO
```

## Версии пакетов Python

Все версии в `requirements.txt` зафиксированы и проверены на совместимость с Python 3.7.3:

| Пакет | Версия | Примечание |
|-------|--------|------------|
| Flask | 2.0.3 | Последняя версия с поддержкой 3.7 |
| SQLAlchemy | 2.0.23 | Требует 3.7+ |
| weasyprint | 52.5 | Последняя полная поддержка 3.7 |
| APScheduler | 3.9.1.post1 | 3.10+ требует 3.8+ |
| python-telegram-bot | 13.15 | 20.0+ требует 3.8+ |
| pandas | 1.3.5 | Последняя стабильная для 3.7 |
| plotly | 5.18.0 | Поддерживает 3.7 |

## Проверка совместимости

### Скрипт проверки
```bash
#!/bin/bash
# check_python.sh

echo "Проверка версии Python..."
python3 --version

# Проверка минимальной версии
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)"
if [ $? -ne 0 ]; then
    echo "❌ Требуется Python 3.7 или выше"
    exit 1
fi

echo "✅ Версия Python подходит"

# Проверка установленных пакетов
echo "Проверка установленных пакетов..."
pip3 check

echo "✅ Все проверки пройдены"
```

## Развёртывание на Debian 10

### 1. Подготовка системы
```bash
sudo apt update
sudo apt upgrade -y
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

### 2. Создание виртуального окружения
```bash
cd /opt/jira_report
python3 -m venv venv
source venv/bin/activate
```

### 3. Установка зависимостей
```bash
pip install --upgrade pip==23.3.1
pip install -r requirements.txt
```

### 4. Инициализация
```bash
python scripts/init_db.py
```

### 5. Проверка
```bash
python -c "
import sys
print(f'Python: {sys.version}')

import sqlalchemy
print(f'SQLAlchemy: {sqlalchemy.__version__}')

import telegram
print(f'python-telegram-bot: {telegram.__version__}')

import apscheduler
print(f'APScheduler: {apscheduler.__version__}')

import weasyprint
print(f'WeasyPrint: {weasyprint.__version__}')
"
```

## Ограничения Python 3.7

### Недоступные конструкции
```python
# ❌ Walrus operator (:=) - Python 3.8+
if (n := len(data)) > 10:
    pass

# ❌ match/case - Python 3.10+
match status:
    case 1: pass

# ❌ typing.Literal, Protocol - Python 3.8+
from typing import Literal, Protocol

# ❌ f-string = для отладки - Python 3.8+
print(f'{value=}')

# ❌ позиционно-именованные аргументы - Python 3.8+
def func(x, /, y, *, z): pass
```

### Доступные конструкции
```python
# ✅ Data classes - Python 3.7+
from dataclasses import dataclass

@dataclass
class Report:
    id: int
    period: str

# ✅ TypedDict - Python 3.7+
from typing import TypedDict

class ReportData(TypedDict):
    id: int
    period: str

# ✅ asyncio - Python 3.7+
import asyncio

async def main():
    await asyncio.sleep(1)

# ✅ typing.Optional, List, Dict - Python 3.7+
from typing import Optional, List, Dict

def process(data: Optional[List[str]]) -> Dict[str, int]:
    pass
```

## Миграция на более новую версию Python

Если в будущем планируется переход на Python 3.8+:

### 1. Обновить requirements.txt
```bash
# Убрать ограничения версий
# python-telegram-bot>=20.0.0
# APScheduler>=3.10.0
# weasyprint>=59.0.0
```

### 2. Обновить код
- Заменить синхронные вызовы на async/await
- Использовать новые возможности typing
- Применить match/case где уместно

### 3. Протестировать
```bash
python3.8 -m pytest tests/
```

## Контакты

По вопросам развёртывания и настройки обращайтесь к администратору системы.

---

**Последнее обновление:** 2024-03-08  
**Версия документа:** 1.0  
**Статус:** Актуально для Debian 10 + Python 3.7.3
