#!/bin/bash

echo "🛑 Остановка Perplexity Bot..."
echo "========================================="

# Функция для безопасной остановки процесса
stop_process() {
    local pid_file=$1
    local service_name=$2
    local process_pattern=$3
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        
        # Проверяем, существует ли процесс
        if kill -0 "$pid" 2>/dev/null; then
            # Пробуем graceful shutdown (SIGTERM)
            if kill -TERM "$pid" 2>/dev/null; then
                echo "📤 Отправлен SIGTERM для $service_name (PID: $pid)"
                
                # Ждем до 5 секунд для graceful shutdown
                local count=0
                while [ $count -lt 5 ] && kill -0 "$pid" 2>/dev/null; do
                    sleep 1
                    count=$((count + 1))
                done
                
                # Если процесс все еще работает, используем SIGKILL
                if kill -0 "$pid" 2>/dev/null; then
                    echo "⚠️  $service_name не остановился, используем SIGKILL"
                    kill -9 "$pid" 2>/dev/null
                    sleep 1
                fi
                
                echo "✅ $service_name остановлен"
            fi
        else
            echo "ℹ️  $service_name не запущен (PID $pid не активен)"
        fi
        
        rm -f "$pid_file"
    else
        echo "ℹ️  PID файл для $service_name не найден"
    fi
    
    # Дополнительная очистка по паттерну процесса
    if [ -n "$process_pattern" ]; then
        local remaining=$(pgrep -f "$process_pattern" 2>/dev/null)
        if [ -n "$remaining" ]; then
            echo "🧹 Очистка оставшихся процессов $service_name"
            pkill -f "$process_pattern" 2>/dev/null
            sleep 1
            # Если все еще есть процессы - используем SIGKILL
            pkill -9 -f "$process_pattern" 2>/dev/null
        fi
    fi
}

# Остановка всех сервисов
stop_process "logs/bot.pid" "Telegram Bot" "python.*bot"
stop_process "logs/server.pid" "Node Server" "node.*server"
stop_process "logs/xvfb.pid" "Xvfb" "Xvfb"

# Остановка Chrome (у него может не быть PID файла)
echo "🌐 Остановка Chrome..."
pkill -f "chrome.*--load-extension=extension" 2>/dev/null
pkill chrome 2>/dev/null
pkill chromium 2>/dev/null

# Очистка Chrome PID если существует
[ -f logs/chrome.pid ] && rm logs/chrome.pid

echo ""
echo "========================================="
echo "✅ Все процессы остановлены"
echo "========================================="