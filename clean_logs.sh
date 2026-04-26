#!/bin/bash

# Простой скрипт для полной очистки всех логов
# Использование: ./clean_logs.sh

LOGS_DIR="logs"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция вывода сообщений
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка существования директории логов
if [ ! -d "$LOGS_DIR" ]; then
    log_error "Директория $LOGS_DIR не существует"
    exit 1
fi

# Подсчет статистики
INITIAL_SIZE=$(du -sh "$LOGS_DIR" 2>/dev/null | cut -f1)
INITIAL_COUNT=$(find "$LOGS_DIR" -type f \( -name "*.log" -o -name "*.gz" -o -name "*.tar.gz" \) 2>/dev/null | wc -l)

echo "========================================"
echo "🗑️  ПОЛНАЯ ОЧИСТКА ЛОГОВ"
echo "========================================"
log_info "Директория: $LOGS_DIR"
log_info "Текущий размер: $INITIAL_SIZE"
log_info "Файлов: $INITIAL_COUNT"
echo ""

read -p "⚠️  Удалить ВСЕ логи? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warn "Отменено"
    exit 0
fi

echo ""
log_info "Удаление всех логов..."

# Сохраняем PID файлы
mkdir -p "$LOGS_DIR/.tmp_pids"
find "$LOGS_DIR" -name "*.pid" -exec cp {} "$LOGS_DIR/.tmp_pids/" \; 2>/dev/null

# Удаляем все логи, архивы и временные файлы
find "$LOGS_DIR" -type f \( \
    -name "*.log" -o \
    -name "*.log.*" -o \
    -name "*.gz" -o \
    -name "*.tar.gz" -o \
    -name "*.tmp" -o \
    -name "*.swp" -o \
    -name "*~" \
\) -delete 2>/dev/null

# Создаем пустые файлы для активных логов
touch "$LOGS_DIR/bot.log"
touch "$LOGS_DIR/server.log" 
touch "$LOGS_DIR/chrome.log"
touch "$LOGS_DIR/errors.log"
touch "$LOGS_DIR/server_errors.log"
touch "$LOGS_DIR/auto_clean.log"

log_info "Созданы пустые файлы для активных логов"

# Восстанавливаем PID файлы
if [ -d "$LOGS_DIR/.tmp_pids" ]; then
    cp "$LOGS_DIR/.tmp_pids/"*.pid "$LOGS_DIR/" 2>/dev/null
    rm -rf "$LOGS_DIR/.tmp_pids"
fi

# Финальная статистика
FINAL_SIZE=$(du -sh "$LOGS_DIR" 2>/dev/null | cut -f1)
FINAL_COUNT=$(find "$LOGS_DIR" -type f \( -name "*.log" -o -name "*.gz" -o -name "*.tar.gz" \) 2>/dev/null | wc -l)

echo ""
echo "========================================"
echo "✅ Очистка завершена!"
echo "========================================"
log_info "Размер до: $INITIAL_SIZE (файлов: $INITIAL_COUNT)"
log_info "Размер после: $FINAL_SIZE (файлов: $FINAL_COUNT)"
echo "========================================"