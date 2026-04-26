#!/bin/bash

# Скрипт для настройки автоматической очистки логов через cron
# Использование: ./setup_cron.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLEAN_SCRIPT="$SCRIPT_DIR/auto_clean_logs.sh"
CRON_TIME="0 3 * * *"  # Каждый день в 3:00 ночи

echo "========================================"
echo "📅 Настройка автоматической очистки логов"
echo "========================================"
echo ""
echo "Скрипт очистки: $CLEAN_SCRIPT"
echo "Расписание: ежедневно в 03:00"
echo ""

# Проверка существования скрипта
if [ ! -f "$CLEAN_SCRIPT" ]; then
    echo "❌ Ошибка: Скрипт $CLEAN_SCRIPT не найден"
    exit 1
fi

# Проверка текущих задач cron
echo "Проверка существующих задач cron..."
EXISTING_CRON=$(crontab -l 2>/dev/null | grep -F "$CLEAN_SCRIPT")

if [ -n "$EXISTING_CRON" ]; then
    echo "⚠️  Задача уже существует в crontab:"
    echo "   $EXISTING_CRON"
    echo ""
    read -p "Хотите обновить расписание? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Отменено"
        exit 0
    fi
    # Удаляем старую задачу
    (crontab -l 2>/dev/null | grep -v -F "$CLEAN_SCRIPT") | crontab -
fi

# Добавление новой задачи
echo "Добавление задачи в crontab..."
(crontab -l 2>/dev/null; echo "$CRON_TIME $CLEAN_SCRIPT") | crontab -

if [ $? -eq 0 ]; then
    echo "✅ Задача успешно добавлена в crontab"
    echo ""
    echo "Текущие задачи cron для очистки логов:"
    crontab -l | grep -F "$CLEAN_SCRIPT"
    echo ""
    echo "========================================"
    echo "📝 Информация:"
    echo "- Логи будут очищаться каждый день в 03:00"
    echo "- Логи старше 7 дней будут удаляться"
    echo "- Большие активные логи будут ротироваться"
    echo "- Лог работы скрипта: logs/auto_clean.log"
    echo ""
    echo "Управление:"
    echo "- Просмотр задач: crontab -l"
    echo "- Редактирование: crontab -e"
    echo "- Удаление всех задач: crontab -r"
    echo "========================================"
else
    echo "❌ Ошибка при добавлении задачи в crontab"
    exit 1
fi