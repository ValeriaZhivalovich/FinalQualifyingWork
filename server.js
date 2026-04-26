const express = require('express');
const { WebSocketServer } = require('ws');
const http = require('http');
const fs = require('fs');
const path = require('path');
const CookiesManager = require('./cookies_manager');
require('./logger'); // Подключаем настройку логирования

const app = express();
// Добавляем обработку JSON с защитой от ошибок парсинга
app.use(express.json({ 
    limit: '10mb',
    verify: (req, res, buf, encoding) => {
        try {
            JSON.parse(buf);
        } catch(e) {
            logger.error('Invalid JSON received:', e.message);
            console.error('Invalid JSON in request body:', buf.toString().substring(0, 100));
            res.status(400).json({ error: 'Invalid JSON format' });
            throw new Error('Invalid JSON');
        }
    }
}));
app.use(express.urlencoded({ limit: '10mb', extended: true }));

const server = http.createServer(app);
const wss = new WebSocketServer({ server });

// Хранилище активных подключений
const connections = new Map();

// Менеджер cookies
const cookiesManager = new CookiesManager();
cookiesManager.setupAutoSave();

// Флаг активного запроса к браузеру
let activeRequest = null;
let activeRequestTime = null;

// Эндпоинт для проверки статуса
app.get('/status', (req, res) => {
    res.json({
        extensionConnected: connections.size > 0,
        activeConnections: connections.size,
        activeRequest: activeRequest !== null
    });
});

// Детальный health check
app.get('/health', async (req, res) => {
    const health = {
        status: 'ok',
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
        memory: process.memoryUsage(),
        checks: {
            server: true,
            websocket: wss.clients.size > 0,
            extension: connections.size > 0,
            cookies: await cookiesManager.hasSavedCookies()
        },
        details: {
            activeConnections: connections.size,
            websocketClients: wss.clients.size,
            activeRequest: activeRequest,
            nodeVersion: process.version,
            platform: process.platform
        }
    };
    
    // Определяем общий статус
    if (!health.checks.server) {
        health.status = 'error';
    } else if (!health.checks.extension || !health.checks.websocket) {
        health.status = 'warning';
    }
    
    const statusCode = health.status === 'ok' ? 200 : 
                       health.status === 'warning' ? 206 : 500;
    
    res.status(statusCode).json(health);
});

// Эндпоинт для управления cookies
app.post('/cookies/save', async (req, res) => {
    const result = await cookiesManager.saveCookies();
    res.json({ success: result });
});

app.post('/cookies/restore', async (req, res) => {
    const result = await cookiesManager.restoreCookies();
    res.json({ success: result });
});

app.get('/cookies/status', async (req, res) => {
    const hasCookies = await cookiesManager.hasSavedCookies();
    res.json({ hasSavedCookies: hasCookies });
});

app.get('/cookies/load', async (req, res) => {
    try {
        await cookiesManager.loadCookies();
        const cookies = cookiesManager.getCookies();
        console.log(`Sending ${cookies.length} cookies to extension`);
        res.json({ cookies: cookies || [] });
    } catch (err) {
        console.error('Error loading cookies:', err);
        res.json({ cookies: [] });
    }
});

// WebSocket соединение с расширением
wss.on('connection', (ws) => {
    const connectionId = Date.now().toString();
    connections.set(connectionId, ws);
    console.log('Extension connected:', connectionId);

    // Отправляем приветственное сообщение
    ws.send(JSON.stringify({ type: 'welcome', connectionId }));

    // Настройка keepalive
    const pingInterval = setInterval(() => {
        if (ws.readyState === ws.OPEN) {
            ws.ping();
        } else {
            clearInterval(pingInterval);
        }
    }, 30000);

    ws.on('message', async (data) => {
        try {
            const message = JSON.parse(data.toString());
            
            // Обработка ping
            if (message.type === 'ping') {
                ws.send(JSON.stringify({ type: 'pong' }));
                return;
            }
            
            // Игнорируем сообщения о скриншотах (функция удалена)
            if (message.type === 'screenshot') {
                return;
            }
        } catch (error) {
            console.error('Error parsing message:', error);
        }
    });

    ws.on('close', () => {
        connections.delete(connectionId);
        console.log('Extension disconnected:', connectionId);
        clearInterval(pingInterval);
        
        // Очищаем активный запрос если соединение разорвано
        if (activeRequest) {
            console.log(`Clearing active request due to disconnection: ${activeRequest}`);
            activeRequest = null;
            activeRequestTime = null;
        }
    });

    ws.on('error', (error) => {
        console.error('WebSocket error:', error);
        // Попытка переподключения не требуется - расширение само переподключится
    });

    ws.on('pong', () => {
        // Расширение живо
    });
});

// Простой API endpoint для тестирования
app.post('/api/message', async (req, res) => {
    try {
        const { message } = req.body;
        
        if (!message) {
            return res.status(400).json({ error: 'Message is required' });
        }
        
        // Преобразуем в формат MCP
        const messages = [{
            role: 'user',
            content: message
        }];
        
        // Дальше используем общую логику
        await handleRequest(messages, 4096, res);
    } catch (error) {
        console.error('❌', error);
        res.status(500).json({ error: error.message });
    }
});

// MCP endpoint
app.post('/v1/messages', async (req, res) => {
    try {
        const { messages, max_tokens = 4096 } = req.body;
        await handleRequest(messages, max_tokens, res);
    } catch (error) {
        console.error('❌', error);
        res.status(500).json({ error: error.message });
    }
});

// Общая функция обработки запросов
async function handleRequest(messages, max_tokens, res) {
    try {
        
        // Проверяем наличие подключенного расширения
        if (connections.size === 0) {
            return res.status(503).json({ 
                error: 'No browser extension connected. Please open Perplexity in your browser.' 
            });
        }

        // Проверяем, нет ли активного запроса
        if (activeRequest) {
            // Проверяем, не завис ли запрос (более 5 минут - как основной таймаут)
            const now = Date.now();
            const STALE_REQUEST_TIMEOUT = 300000; // 5 минут
            if (activeRequestTime && (now - activeRequestTime) > STALE_REQUEST_TIMEOUT) {
                console.log(`Clearing stale request ${activeRequest} (age: ${now - activeRequestTime}ms)`);
                activeRequest = null;
                activeRequestTime = null;
            } else {
                console.log(`Request rejected - browser is busy with request ${activeRequest}`);
                console.log(`Current time: ${new Date().toISOString()}`);
                console.log(`Active request age: ${activeRequestTime ? now - activeRequestTime : 'unknown'}ms`);
                return res.status(429).json({ 
                    error: 'Browser is busy processing another request. Please try again later.',
                    activeRequest: activeRequest
                });
            }
        }

        // Берем первое активное соединение
        const [connectionId, ws] = connections.entries().next().value;
        
        // Создаем запрос для расширения
        const requestId = `req_${Date.now()}`;
        const extensionRequest = {
            id: requestId,
            type: 'chat',
            messages: messages,
            max_tokens: max_tokens
        };

        // Устанавливаем флаг активного запроса
        activeRequest = requestId;
        activeRequestTime = Date.now();
        console.log(`Setting active request: ${requestId} at ${new Date().toISOString()}`);

        // Отправляем запрос в расширение
        ws.send(JSON.stringify(extensionRequest));

        // Ждем ответ от расширения
        console.log(`Waiting for response from extension for request ${requestId}...`);
        
        let response;
        try {
            response = await new Promise((resolve, reject) => {
                // Увеличиваем таймаут до 5 минут для долгих генераций
                const TIMEOUT_MS = 300000; // 5 минут
                const timeout = setTimeout(() => {
                    logger.error(`Request timeout for ${requestId} after ${TIMEOUT_MS/1000} seconds`);
                    console.log(`Timeout for request ${requestId} after ${TIMEOUT_MS/1000} seconds`);
                    ws.removeListener('message', messageHandler);
                    // Очищаем активный запрос при таймауте
                    if (activeRequest === requestId) {
                        activeRequest = null;
                        activeRequestTime = null;
                        console.log(`Cleared active request on timeout: ${requestId}`);
                    }
                    reject(new Error('Request timeout'));
                }, TIMEOUT_MS); // Таймаут 5 минут

                const messageHandler = (data) => {
                    try {
                        const message = JSON.parse(data.toString());
                        console.log(`Received message from extension:`, message);
                        if (message.id === requestId) {
                            console.log(`Response matched request ${requestId}:`, message);
                            clearTimeout(timeout);
                            ws.removeListener('message', messageHandler);
                            resolve(message);
                        }
                    } catch (error) {
                        console.error('Error parsing message:', error);
                        // Важно: не очищаем флаг здесь, так как запрос все еще активен
                    }
                };

                ws.on('message', messageHandler);
            });
        } catch (error) {
            console.error(`Error waiting for response: ${error.message}`);
            // Очищаем флаг активного запроса при ошибке
            if (activeRequest === requestId) {
                activeRequest = null;
                activeRequestTime = null;
                console.log(`Cleared active request on error: ${requestId}`);
            }
            return res.status(500).json({ error: error.message });
        }

        // Очищаем флаг активного запроса после успешного получения ответа
        if (activeRequest === requestId) {
            activeRequest = null;
            activeRequestTime = null;
            console.log(`Cleared active request after success: ${requestId}`);
        }

        // Проверяем что ответ получен
        if (!response) {
            console.log('Response is null or undefined');
            return res.status(500).json({ error: 'Empty response from extension' });
        }

        // Проверяем на ошибки
        if (response.error) {
            console.log(`Error in response: ${response.error}`);
            return res.status(500).json({ error: response.error });
        }

        // Получаем контент из ответа
        console.log(`Processing response structure:`, {
            hasContent: !!response.content,
            contentType: typeof response.content,
            isArray: Array.isArray(response.content),
            responseKeys: Object.keys(response)
        });

        let content;
        if (response.content && Array.isArray(response.content)) {
            // Если content уже в нужном формате
            console.log(`Using array content with ${response.content.length} items`);
            content = response.content;
        } else if (response.content && typeof response.content === 'string') {
            // Если content - это строка, оборачиваем в массив
            console.log(`Converting string content to array (length: ${response.content.length})`);
            content = [{
                type: 'text',
                text: response.content
            }];
        } else if (typeof response === 'string') {
            // Если весь ответ - это строка
            console.log(`Using entire response as string (length: ${response.length})`);
            content = [{
                type: 'text',
                text: response
            }];
        } else {
            // Если ничего нет
            console.log(`No valid content found, using empty response`);
            content = [{
                type: 'text',
                text: 'Ответ пуст'
            }];
        }

        console.log(`Final formatted content:`, content);

        // Форматируем ответ для MCP
        const mcpResponse = {
            id: `msg_${Date.now()}`,
            type: 'message',
            role: 'assistant',
            content: content,
            model: 'perplexity',
            stop_reason: 'end_turn',
            stop_sequence: null,
            usage: {
                input_tokens: 0,
                output_tokens: 0
            }
        };

        res.json(mcpResponse);
    } catch (error) {
        console.error('Error:', error);
        // Очищаем флаг активного запроса при ошибке (используем текущий activeRequest)
        if (activeRequest) {
            console.log(`Cleared active request on error: ${activeRequest}`);
            activeRequest = null;
            activeRequestTime = null;
        }
        res.status(500).json({ error: error.message });
    }
}

// Обработка ошибок процесса
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
    // Не завершаем процесс, пытаемся продолжить работу
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
    // Не завершаем процесс, пытаемся продолжить работу
});

// Graceful shutdown
process.on('SIGTERM', () => {
    console.log('SIGTERM received, closing connections...');
    connections.forEach(ws => ws.close());
    wss.close(() => {
        server.close(() => {
            process.exit(0);
        });
    });
});

process.on('SIGINT', () => {
    console.log('SIGINT received, closing connections...');
    connections.forEach(ws => ws.close());
    wss.close(() => {
        server.close(() => {
            process.exit(0);
        });
    });
});

// Запуск сервера
const PORT = process.env.SERVER_PORT || 3002;
const HOST = process.env.SERVER_HOST || '0.0.0.0';

// Устанавливаем таймауты для HTTP сервера
server.timeout = 310000; // 5 минут 10 секунд (чуть больше основного таймаута)
server.keepAliveTimeout = 310000; // Keep-alive соединения
server.headersTimeout = 315000; // Таймаут для заголовков

server.listen(PORT, HOST, () => {
    console.log(`Perplexity browser bridge running on ${HOST}:${PORT}`);
    console.log('WebSocket server ready for extension connections');
    console.log(`Server timeout: ${server.timeout/1000}s, Keep-alive: ${server.keepAliveTimeout/1000}s`);
    console.log('Environment:', process.env.NODE_ENV || 'development');
});