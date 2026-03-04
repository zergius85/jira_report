#!/bin/bash
# =============================================
# РЎРєСЂРёРїС‚ СѓСЃС‚Р°РЅРѕРІРєРё СЃР»СѓР¶Р±С‹ Jira Report Web
# Р—Р°РїСѓСЃРєР°С‚СЊ РѕС‚ root С‡РµСЂРµР· sudo
# =============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="jira-report"

echo "рџ”§ РЈСЃС‚Р°РЅРѕРІРєР° СЃР»СѓР¶Р±С‹ $SERVICE_NAME..."

# РџСЂРѕРІРµСЂРєР° РїСЂР°РІ root
if [ "$EUID" -ne 0 ]; then
    echo "вќЊ Р—Р°РїСѓСЃС‚РёС‚Рµ СЃРєСЂРёРїС‚ С‡РµСЂРµР· sudo:"
    echo "   sudo ./install-service.sh"
    exit 1
fi

# РџСЂРѕРІРµСЂРєР° .env
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "вљ пёЏ  Р¤Р°Р№Р» .env РЅРµ РЅР°Р№РґРµРЅ!"
    echo "   РЎРѕР·РґР°Р№С‚Рµ .env РїРµСЂРµРґ СѓСЃС‚Р°РЅРѕРІРєРѕР№ СЃР»СѓР¶Р±С‹:"
    echo "   cp .env.example .env"
    exit 1
fi

# РџСЂРѕРІРµСЂРєР° config.py
if [ ! -f "$SCRIPT_DIR/config.py" ]; then
    echo "вќЊ Р¤Р°Р№Р» config.py РЅРµ РЅР°Р№РґРµРЅ!"
    echo "   РЈР±РµРґРёС‚РµСЃСЊ, С‡С‚Рѕ config.py СЃСѓС‰РµСЃС‚РІСѓРµС‚ РІ РґРёСЂРµРєС‚РѕСЂРёРё СЃР»СѓР¶Р±С‹"
    exit 1
fi

# РљРѕРїРёСЂРѕРІР°РЅРёРµ С„Р°Р№Р»Р° СЃР»СѓР¶Р±С‹
cp "$SCRIPT_DIR/${SERVICE_NAME}.service" "/etc/systemd/system/${SERVICE_NAME}.service"

echo "вњ… Р¤Р°Р№Р» СЃР»СѓР¶Р±С‹ СЃРєРѕРїРёСЂРѕРІР°РЅ"

# РџРµСЂРµР·Р°РіСЂСѓР·РєР° systemd
systemctl daemon-reload

# Р’РєР»СЋС‡РµРЅРёРµ Рё Р·Р°РїСѓСЃРє СЃР»СѓР¶Р±С‹
systemctl enable ${SERVICE_NAME}.service
systemctl start ${SERVICE_NAME}.service

echo "вњ… РЎР»СѓР¶Р±Р° СѓСЃС‚Р°РЅРѕРІР»РµРЅР° Рё Р·Р°РїСѓС‰РµРЅР°"
echo ""
echo "рџ“Љ РЎС‚Р°С‚СѓСЃ СЃР»СѓР¶Р±С‹:"
systemctl status ${SERVICE_NAME}.service --no-pager
echo ""
echo "рџ“ќ РџСЂРѕСЃРјРѕС‚СЂ Р»РѕРіРѕРІ:"
echo "   journalctl -u ${SERVICE_NAME}.service -f"
echo ""
echo "рџ”§ РЈРїСЂР°РІР»РµРЅРёРµ СЃР»СѓР¶Р±РѕР№:"
echo "   sudo systemctl start ${SERVICE_NAME}.service     # Р—Р°РїСѓСЃС‚РёС‚СЊ"
echo "   sudo systemctl stop ${SERVICE_NAME}.service      # РћСЃС‚Р°РЅРѕРІРёС‚СЊ"
echo "   sudo systemctl restart ${SERVICE_NAME}.service   # РџРµСЂРµР·Р°РїСѓСЃС‚РёС‚СЊ"
echo "   sudo systemctl disable ${SERVICE_NAME}.service   # РћС‚РєР»СЋС‡РёС‚СЊ"
