#!/bin/bash

# Скрипт полной очистки Perplexity Bot с сервера
# ВНИМАНИЕ: Этот скрипт удалит ВСЕ данные бота с сервера!

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${RED}⚠️  ВНИМАНИЕ! ПОЛНАЯ ОЧИСТКА PERPLEXITY BOT С СЕРВЕРА${NC}"
echo "=================================================="
echo ""
echo "Этот скрипт выполнит следующие действия на сервере 91.132.57.25:"
echo "1. Остановит и удалит ВСЕ Docker контейнеры бота"
echo "2. Удалит ВСЕ Docker образы бота"
echo "3. Удалит ВСЕ файлы из /opt/perplexity-bot"
echo "4. Очистит Docker систему от неиспользуемых ресурсов"
echo ""
echo -e "${YELLOW}Все данные будут БЕЗВОЗВРАТНО УДАЛЕНЫ!${NC}"
echo ""
read -p "Вы уверены? Введите 'YES' для продолжения: " confirmation

if [ "$confirmation" != "YES" ]; then
    echo -e "${GREEN}Отменено пользователем${NC}"
    exit 0
fi

echo ""
echo -e "${YELLOW}🔧 Подключение к серверу и очистка...${NC}"

ssh root@91.132.57.25 'bash -s' << 'ENDSSH'
set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🛑 Остановка контейнеров...${NC}"
cd /opt/perplexity-bot 2>/dev/null || true

# Останавливаем через docker-compose если есть
if [ -f docker-compose.yml ]; then
    docker compose down 2>/dev/null || true
fi

# Останавливаем и удаляем контейнер по имени
docker stop perplexity-bot 2>/dev/null || true
docker rm -f perplexity-bot 2>/dev/null || true

# Останавливаем ВСЕ контейнеры с именем содержащим perplexity
docker ps -a | grep perplexity | awk '{print $1}' | xargs -r docker stop 2>/dev/null || true
docker ps -a | grep perplexity | awk '{print $1}' | xargs -r docker rm -f 2>/dev/null || true

echo -e "${YELLOW}🗑️ Удаление Docker образов...${NC}"
# Удаляем образы
docker images | grep perplexity | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true

echo -e "${YELLOW}📁 Удаление файлов...${NC}"
# Сохраняем список файлов перед удалением
if [ -d /opt/perplexity-bot ]; then
    echo "Удаляемые файлы:"
    ls -la /opt/perplexity-bot/ 2>/dev/null || true
    echo ""
    
    # Удаляем все файлы
    rm -rf /opt/perplexity-bot/*
    rm -rf /opt/perplexity-bot/.*  2>/dev/null || true
    
    # Проверяем что директория пуста
    if [ -z "$(ls -A /opt/perplexity-bot 2>/dev/null)" ]; then
        echo -e "${GREEN}✅ Директория /opt/perplexity-bot очищена${NC}"
    else
        echo -e "${YELLOW}Остались файлы:${NC}"
        ls -la /opt/perplexity-bot/
    fi
else
    echo "Директория /opt/perplexity-bot не существует"
fi

echo -e "${YELLOW}🧹 Очистка Docker системы...${NC}"
docker system prune -af --volumes

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ ОЧИСТКА ЗАВЕРШЕНА УСПЕШНО!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Проверка:"
echo "Docker контейнеры:"
docker ps -a | grep perplexity || echo "Нет контейнеров perplexity"
echo ""
echo "Docker образы:"
docker images | grep perplexity || echo "Нет образов perplexity"
echo ""
echo "Файлы в /opt/perplexity-bot:"
ls -la /opt/perplexity-bot 2>/dev/null || echo "Директория пуста или не существует"

ENDSSH

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✅ СЕРВЕР ПОЛНОСТЬЮ ОЧИЩЕН!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Теперь можно выполнить новый деплой командой:"
    echo -e "${YELLOW}./auto_deploy.sh${NC}"
else
    echo -e "${RED}❌ Ошибка при очистке сервера${NC}"
    exit 1
fi