#!/bin/bash

# Полный запуск системы Perplexity Bot с расширением Chrome
# Использование: ./start.sh [local|server] [-d]

MODE=${1:-local}

echo "🚀 Запуск Perplexity Bot с расширением Chrome ($MODE mode)"
echo "========================================="

# Функция для проверки и очистки старых PID файлов
cleanup_old_pids() {
    local pid_file=$1
    local service_name=$2
    
    if [ -f "$pid_file" ]; then
        local old_pid=$(cat "$pid_file")
        if ! kill -0 "$old_pid" 2>/dev/null; then
            echo "🧹 Очистка старого PID файла для $service_name (PID $old_pid не активен)"
            rm -f "$pid_file"
        else
            echo "⚠️  $service_name уже запущен с PID $old_pid"
            echo "   Используйте ./stop.sh для остановки или добавьте --force для перезапуска"
            return 1
        fi
    fi
    return 0
}

# Проверка флага --force
FORCE_RESTART=false
for arg in "$@"; do
    if [ "$arg" == "--force" ]; then
        FORCE_RESTART=true
        echo "🔄 Режим принудительного перезапуска"
        break
    fi
done

# Очистка старых PID файлов или остановка при --force
if [ "$FORCE_RESTART" = true ]; then
    ./stop.sh 2>/dev/null
else
    # Проверяем каждый сервис отдельно
    cleanup_old_pids "logs/server.pid" "Server" || exit 1
    cleanup_old_pids "logs/bot.pid" "Bot" || exit 1
    cleanup_old_pids "logs/chrome.pid" "Chrome" || exit 1
    cleanup_old_pids "logs/xvfb.pid" "Xvfb" || exit 1
fi

# Создание директории логов
mkdir -p logs

# Загрузка переменных окружения
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ Переменные окружения загружены"
fi

# Настройка режима
if [ "$MODE" == "server" ]; then
    export BROWSER_HEADLESS=true
    export DISPLAY=:99
    
    # Запуск виртуального дисплея для серверного режима
    echo "🖥️  Запуск виртуального дисплея..."
    pkill Xvfb 2>/dev/null
    Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
    XVFB_PID=$!
    echo "✅ Xvfb запущен (PID: $XVFB_PID)"
    sleep 2
else
    export BROWSER_HEADLESS=false
    echo "📱 Режим разработки (с GUI)"
fi

# Запуск основного сервера для работы с расширением Chrome
echo ""
echo "🌐 Запуск сервера для расширения Chrome..."
node server.js > logs/server.log 2>&1 &
SERVER_PID=$!
echo "✅ Сервер запущен (PID: $SERVER_PID)"

# Ждём инициализации сервера
echo "⏳ Ожидание инициализации сервера..."
for i in {1..10}; do
    if curl -s http://localhost:3002/status > /dev/null 2>&1; then
        STATUS=$(curl -s http://localhost:3002/status)
        echo "✅ Сервер готов: $STATUS"
        break
    fi
    echo -n "."
    sleep 1
done

# Запуск Chrome с расширением
echo ""
echo "🌐 Запуск Chrome с расширением..."
if [ "$MODE" = "server" ]; then
    # Режим для сервера - НЕ headless, но на виртуальном дисплее
    DISPLAY=:99 google-chrome \
        --no-sandbox \
        --disable-dev-shm-usage \
        --disable-gpu \
        --user-data-dir=chrome_profile \
        --load-extension=extension \
        --disable-blink-features=AutomationControlled \
        --window-size=1920,1080 \
        --start-maximized \
        https://www.perplexity.ai/spaces/crypto-asistant-T51ZY9NXQUunuH1GpXVkzg > logs/chrome.log 2>&1 &
    CHROME_PID=$!
    echo "✅ Chrome запущен на виртуальном дисплее (PID: $CHROME_PID)"
else
    # GUI режим для локальной разработки
    google-chrome \
        --user-data-dir=chrome_profile \
        --load-extension=extension \
        --disable-blink-features=AutomationControlled \
        https://www.perplexity.ai/spaces/crypto-asistant-T51ZY9NXQUunuH1GpXVkzg > logs/chrome.log 2>&1 &
    CHROME_PID=$!
    echo "✅ Chrome запущен с GUI (PID: $CHROME_PID)"
fi

# Ждем подключения расширения
echo "⏳ Ожидание подключения расширения..."
for i in {1..30}; do
    STATUS=$(curl -s http://localhost:3002/status)
    if echo "$STATUS" | grep -q '"extensionConnected":true'; then
        echo "✅ Расширение подключено!"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo "⚠️  Расширение не подключилось за 30 секунд"
    fi
done

# Запуск Telegram бота
# Проверяем обе возможные переменные (BOT_TOKEN и TELEGRAM_BOT_TOKEN)
BOT_TOKEN_VAR="${TELEGRAM_BOT_TOKEN:-$BOT_TOKEN}"
if [ -n "$BOT_TOKEN_VAR" ]; then
    echo ""
    echo "🤖 Запуск Telegram бота..."
    
    # Экспортируем BOT_TOKEN для бота
    export BOT_TOKEN="$BOT_TOKEN_VAR"
    
    # Используем venv если существует
    if [ -f "./venv/bin/python3" ]; then
        ./venv/bin/python3 -m bot > logs/bot.log 2>&1 &
    else
        python3 -m bot > logs/bot.log 2>&1 &
    fi
    BOT_PID=$!
    
    # Проверяем что бот действительно запустился
    sleep 3
    if kill -0 "$BOT_PID" 2>/dev/null; then
        echo "✅ Telegram бот запущен (PID: $BOT_PID)"
        # НЕ записываем PID здесь - бот сам запишет свой PID через pid_lock
    else
        echo "❌ Не удалось запустить Telegram бота"
        echo "   Проверьте логи: tail -f logs/bot.log"
        BOT_PID=""
    fi
else
    echo "⚠️  TELEGRAM_BOT_TOKEN не установлен"
    echo "   Telegram бот не будет запущен"
fi

# Сохранение PID'ов
echo "$SERVER_PID" > logs/server.pid
# BOT_PID не сохраняем - бот сам управляет своим PID файлом через pid_lock
[ -n "$XVFB_PID" ] && echo "$XVFB_PID" > logs/xvfb.pid

echo ""
echo "========================================="
echo "✅ Система запущена!"
echo ""
echo "📊 Статус сервера: http://localhost:3002/status"
echo ""
echo "📋 Логи:"
echo "  - Сервер: tail -f logs/server.log"
echo "  - Telegram бот: tail -f logs/bot.log"
echo ""
echo "🛑 Для остановки: ./stop.sh"
echo "========================================="
echo ""

# Если не в фоновом режиме, ждём
if [ "$2" != "-d" ]; then
    echo "Нажмите Ctrl+C для остановки..."
    
    # Обработчик Ctrl+C
    trap './stop.sh; exit' INT
    
    # Ждём завершения процессов
    tail -f /dev/null
fi