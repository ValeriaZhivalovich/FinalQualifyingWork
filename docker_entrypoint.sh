#!/bin/bash

# Скрипт точки входа для Docker контейнера с graceful shutdown

# Цвета для логов
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[DOCKER]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[DOCKER]${NC} $1"
}

log_error() {
    echo -e "${RED}[DOCKER]${NC} $1"
}

# PID'ы процессов
XVFB_PID=""
VNC_PID=""
WEBSOCKIFY_PID=""
SERVER_PID=""
CHROME_PID=""
BOT_PID=""

# Функция для завершения всех процессов
cleanup() {
    log_warn "Получен сигнал завершения, останавливаем все процессы..."
    
    # Останавливаем бота первым (graceful)
    if [ -n "$BOT_PID" ] && kill -0 $BOT_PID 2>/dev/null; then
        log_info "Останавливаем бота (PID: $BOT_PID)..."
        kill -TERM $BOT_PID
        
        # Ждем до 10 секунд graceful shutdown
        for i in {1..10}; do
            if ! kill -0 $BOT_PID 2>/dev/null; then
                log_info "Бот остановлен"
                break
            fi
            sleep 1
        done
        
        # Если все еще жив - убиваем
        if kill -0 $BOT_PID 2>/dev/null; then
            log_warn "Принудительная остановка бота..."
            kill -KILL $BOT_PID
        fi
    fi
    
    # Останавливаем Chrome
    if [ -n "$CHROME_PID" ] && kill -0 $CHROME_PID 2>/dev/null; then
        log_info "Останавливаем Chrome (PID: $CHROME_PID)..."
        kill -TERM $CHROME_PID
        sleep 2
    fi
    
    # Останавливаем сервер
    if [ -n "$SERVER_PID" ] && kill -0 $SERVER_PID 2>/dev/null; then
        log_info "Останавливаем сервер (PID: $SERVER_PID)..."
        kill -TERM $SERVER_PID
        sleep 1
    fi
    
    # Останавливаем VNC компоненты
    if [ -n "$WEBSOCKIFY_PID" ] && kill -0 $WEBSOCKIFY_PID 2>/dev/null; then
        log_info "Останавливаем websockify..."
        kill -TERM $WEBSOCKIFY_PID
    fi
    
    if [ -n "$VNC_PID" ] && kill -0 $VNC_PID 2>/dev/null; then
        log_info "Останавливаем VNC..."
        kill -TERM $VNC_PID
    fi
    
    if [ -n "$XVFB_PID" ] && kill -0 $XVFB_PID 2>/dev/null; then
        log_info "Останавливаем Xvfb..."
        kill -TERM $XVFB_PID
    fi
    
    # Убиваем все оставшиеся Python процессы бота
    log_info "Проверяем оставшиеся процессы бота..."
    pkill -f "python.*bot" 2>/dev/null
    
    # Очищаем PID файлы
    rm -f /app/logs/*.pid 2>/dev/null
    
    log_info "Все процессы остановлены"
    exit 0
}

# Устанавливаем обработчики сигналов
trap cleanup SIGTERM SIGINT SIGQUIT

# Запуск основных компонентов
log_info "Запуск Docker контейнера..."

# Очистка старых блокировок
rm -f /tmp/.X99-lock 2>/dev/null
rm -rf /app/chrome_profile/Singleton* 2>/dev/null
rm -f /app/logs/*.pid 2>/dev/null

# Импорт cookies
log_info "Импорт cookies..."
if [ -f /app/cookies.json ]; then
    python3 /app/import_cookies.py && log_info "Cookies импортированы" || log_warn "Ошибка импорта cookies"
else
    log_warn "Файл cookies.json не найден"
fi

# Запуск Xvfb
log_info "Запуск Xvfb..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
sleep 2

# Запуск VNC сервера
log_info "Запуск VNC сервера..."
x11vnc -display :99 -nopw -forever -shared -rfbport 5900 &
VNC_PID=$!
sleep 1

# Запуск websockify для noVNC
websockify --web=/usr/share/novnc/ 6080 localhost:5900 &
WEBSOCKIFY_PID=$!
sleep 1

# Запуск Node.js сервера
log_info "Запуск сервера..."
node server.js > logs/server.log 2>&1 &
SERVER_PID=$!
sleep 3

# Запуск Chrome с расширением
log_info "Запуск Chrome с расширением..."
google-chrome \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    --user-data-dir=/app/chrome_profile \
    --load-extension=/app/extension \
    --enable-extensions \
    --enable-extension-activity-logging \
    --enable-automation \
    --window-size=1920,1080 \
    --start-maximized \
    --disable-blink-features=AutomationControlled \
    https://www.perplexity.ai/spaces/crypto-asistant-T51ZY9NXQUunuH1GpXVkzg > logs/chrome.log 2>&1 &
CHROME_PID=$!

# Ждем подключения расширения
log_info "Ожидание подключения расширения..."
for i in {1..30}; do
    if curl -s http://localhost:3002/status | grep -q '"extensionConnected":true'; then
        log_info "Расширение подключено!"
        break
    fi
    sleep 1
done

# Запуск бота Python
log_info "Запуск Telegram бота..."
./venv/bin/python3 -m bot &
BOT_PID=$!

log_info "Все компоненты запущены"
log_info "PID'ы процессов:"
log_info "  Xvfb: $XVFB_PID"
log_info "  VNC: $VNC_PID"
log_info "  WebSockify: $WEBSOCKIFY_PID"
log_info "  Server: $SERVER_PID"
log_info "  Chrome: $CHROME_PID"
log_info "  Bot: $BOT_PID"

# Ждем завершения любого из критических процессов
log_info "Контейнер запущен и работает. Для остановки используйте docker stop"

# Мониторим критические процессы и перезапускаем их при необходимости
while true; do
    # Проверяем бота
    if [ -n "$BOT_PID" ] && ! kill -0 $BOT_PID 2>/dev/null; then
        log_warn "Бот остановился, перезапускаем..."
        # Очищаем старый PID файл
        rm -f /app/logs/bot.pid 2>/dev/null
        # Перезапускаем бота
        ./venv/bin/python3 -m bot &
        BOT_PID=$!
        log_info "Бот перезапущен (PID: $BOT_PID)"
        # Ждем немного перед следующей проверкой
        sleep 10
    fi
    
    # Проверяем сервер
    if [ -n "$SERVER_PID" ] && ! kill -0 $SERVER_PID 2>/dev/null; then
        log_warn "Сервер остановился, перезапускаем..."
        node server.js > logs/server.log 2>&1 &
        SERVER_PID=$!
        log_info "Сервер перезапущен (PID: $SERVER_PID)"
        sleep 5
    fi
    
    # Проверяем Chrome
    if [ -n "$CHROME_PID" ] && ! kill -0 $CHROME_PID 2>/dev/null; then
        log_warn "Chrome остановился, перезапускаем..."
        # Очищаем блокировки Chrome
        rm -rf /app/chrome_profile/Singleton* 2>/dev/null
        google-chrome \
            --no-sandbox \
            --disable-dev-shm-usage \
            --disable-gpu \
            --user-data-dir=/app/chrome_profile \
            --load-extension=/app/extension \
            --enable-extensions \
            --window-size=1920,1080 \
            --start-maximized \
            --disable-blink-features=AutomationControlled \
            https://www.perplexity.ai/spaces/crypto-asistant-T51ZY9NXQUunuH1GpXVkzg > logs/chrome.log 2>&1 &
        CHROME_PID=$!
        log_info "Chrome перезапущен (PID: $CHROME_PID)"
        sleep 10
    fi
    
    sleep 5
done