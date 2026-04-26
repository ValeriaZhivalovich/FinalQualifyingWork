FROM ubuntu:22.04

# Отключаем интерактивные запросы при установке
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Установка необходимых пакетов
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    wget \
    gnupg \
    xvfb \
    x11vnc \
    curl \
    scrot \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Установка рабочих версий noVNC и websockify
RUN pip3 install websockify && \
    cd /usr/share && \
    wget -q https://github.com/novnc/noVNC/archive/v1.1.0.tar.gz && \
    tar xzf v1.1.0.tar.gz && \
    mv noVNC-1.1.0 novnc && \
    rm v1.1.0.tar.gz && \
    ln -s /usr/share/novnc/vnc_lite.html /usr/share/novnc/index.html

# Установка Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копирование файлов (с учетом .dockerignore)
COPY . .

# Установка зависимостей Node.js с таймаутом
RUN timeout 120 npm install || echo "WARNING: npm install failed or timed out"

# Создание venv и установка Python зависимостей
RUN python3 -m venv venv && \
    ./venv/bin/pip install --upgrade pip && \
    ./venv/bin/pip install -r requirements.txt

# Создание директорий
RUN mkdir -p logs chrome_profile/Default

# Права на скрипты
RUN chmod +x start.sh stop.sh

# Предустановка расширения в профиль Chrome
RUN mkdir -p /app/chrome_profile/Default/Extensions/ghbmnnjooekpmoecnohmmiedfenbfclp/2.3_0 && \
    cp -r /app/extension/* /app/chrome_profile/Default/Extensions/ghbmnnjooekpmoecnohmmiedfenbfclp/2.3_0/

# Настройка Preferences для автозагрузки расширения
RUN echo '{"extensions":{"settings":{"ghbmnnjooekpmoecnohmmiedfenbfclp":{"location":1,"manifest":{"name":"Perplexity Space Bridge","permissions":["activeTab","scripting","tabs","storage","cookies"],"version":"2.3"},"path":"ghbmnnjooekpmoecnohmmiedfenbfclp/2.3_0","state":1}}}}' > /app/chrome_profile/Default/Preferences

# Переменные окружения
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1
ENV SERVER_MODE=true

EXPOSE 3002 5900 6080

# Используем docker_entrypoint.sh если он существует, иначе старый метод
CMD ["bash", "-c", "\
    if [ -f /app/docker_entrypoint.sh ]; then \
        chmod +x /app/docker_entrypoint.sh && \
        exec /app/docker_entrypoint.sh; \
    else \
        rm -f /tmp/.X99-lock 2>/dev/null && \
    rm -rf /app/chrome_profile/Singleton* 2>/dev/null && \
    echo 'Импорт cookies...' && \
    if [ -f /app/cookies.json ]; then \
        python3 /app/import_cookies.py && echo 'Cookies импортированы' || echo 'Ошибка импорта cookies'; \
    else \
        echo 'Файл cookies.json не найден, пропускаем импорт'; \
    fi && \
    echo 'Запуск Xvfb...' && \
    Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset & \
    sleep 2 && \
    echo 'Запуск VNC сервера...' && \
    x11vnc -display :99 -nopw -forever -shared -rfbport 5900 & \
    sleep 1 && \
    websockify --web=/usr/share/novnc/ 6080 localhost:5900 & \
    sleep 1 && \
    node server.js > logs/server.log 2>&1 & \
    sleep 3 && \
    echo 'Запуск Chrome с расширением...' && \
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
        https://www.perplexity.ai/spaces/crypto-asistant-T51ZY9NXQUunuH1GpXVkzg > logs/chrome.log 2>&1 & \
    sleep 30 && \
    echo 'Проверка подключения расширения...' && \
    curl -s http://localhost:3002/status && \
    echo '' && \
    ./venv/bin/python3 -m bot; \
    fi \
"]