console.log('BACKGROUND.JS LOADED AT', new Date().toISOString());

let ws = null;
let reconnectTimeout = null;
let messageQueue = [];
let isProcessing = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 100;

function connectWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) return;
    
    // Закрываем старое соединение
    if (ws) {
        ws.close();
        ws = null;
    }
    
    try {
        ws = new WebSocket('ws://localhost:3002');
        
        ws.onopen = () => {
            console.log('Connected to MCP server');
            reconnectAttempts = 0; // Сброс счетчика при успешном подключении
            if (reconnectTimeout) {
                clearTimeout(reconnectTimeout);
                reconnectTimeout = null;
            }
            
            // Загружаем куки при первом подключении с задержкой
            setTimeout(() => loadCookiesFromServer(), 2000);
            
            // Отправляем ping каждые 30 секунд
            setInterval(() => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'ping' }));
                }
            }, 30000);
            
            // Обрабатываем накопившуюся очередь
            processQueue();
        };
        
        ws.onmessage = async (event) => {
            try {
                const request = JSON.parse(event.data);
                console.log('Received request:', request);
                console.log('Current queue length before push:', messageQueue.length);
                console.log('Current isProcessing state:', isProcessing);
                
                // Игнорируем pong
                if (request.type === 'pong') return;
                
                // Добавляем запрос в очередь
                messageQueue.push(request);
                console.log('Request added to queue. New queue length:', messageQueue.length);
                processQueue();
                
            } catch (error) {
                console.error('Error handling request:', error);
            }
        };
        
        ws.onclose = () => {
            console.log('Disconnected from MCP server');
            ws = null;
            if (!reconnectTimeout && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                const delay = Math.min(2000 * Math.pow(1.5, reconnectAttempts), 30000); // Экспоненциальная задержка до 30 сек
                console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
                reconnectTimeout = setTimeout(connectWebSocket, delay);
            }
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    } catch (error) {
        console.error('Failed to connect:', error);
        if (!reconnectTimeout && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts++;
            const delay = Math.min(2000 * Math.pow(1.5, reconnectAttempts), 30000);
            console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
            reconnectTimeout = setTimeout(connectWebSocket, delay);
        }
    }
}

// Обработка очереди сообщений
async function processQueue() {
    console.log('[QUEUE] processQueue called. isProcessing:', isProcessing, 'queue length:', messageQueue.length);
    
    if (isProcessing || messageQueue.length === 0) {
        if (isProcessing) {
            console.log('[QUEUE] Already processing, skipping...');
        } else {
            console.log('[QUEUE] Queue is empty');
        }
        return;
    }
    
    isProcessing = true;
    
    while (messageQueue.length > 0) {
        const request = messageQueue.shift();
        console.log('[QUEUE] Processing request:', request.id);
        
        try {
            // Определяем URL нужного Space
            const SPACE_URL = 'https://www.perplexity.ai/spaces/crypto-asistant-T51ZY9NXQUunuH1GpXVkzg';
            
            // Сначала ищем любую вкладку с нужным пространством
            let spaceTabs = await chrome.tabs.query({ 
                url: SPACE_URL + '*'
            });
            
            // Если нет вкладок с нужным пространством, ищем любую вкладку Perplexity
            if (spaceTabs.length === 0) {
                console.log('No space tab found, checking for any Perplexity tabs...');
                const perplexityTabs = await chrome.tabs.query({
                    url: 'https://www.perplexity.ai/*'
                });
                
                if (perplexityTabs.length > 0) {
                    console.log('Found Perplexity tab, navigating to space...');
                    // Переходим на нужный Space
                    await chrome.tabs.update(perplexityTabs[0].id, { url: SPACE_URL });
                    // Ждем загрузки дольше чтобы избежать 429
                    await new Promise(resolve => setTimeout(resolve, 5000));
                    spaceTabs = [perplexityTabs[0]];
                } else {
                    // Создаем новую вкладку с нужным Space
                    console.log('No Perplexity tabs found, creating new tab...');
                    const newTab = await chrome.tabs.create({ url: SPACE_URL });
                    await new Promise(resolve => setTimeout(resolve, 5000));
                    spaceTabs = [newTab];
                }
            }
            
            if (spaceTabs.length === 0) {
                ws.send(JSON.stringify({
                    id: request.id,
                    error: 'Failed to open Perplexity Space.'
                }));
                continue;
            }
            
            // Берем первую вкладку и активируем её
            const tab = spaceTabs[0];
            await chrome.tabs.update(tab.id, { active: true });
            console.log('Using tab:', tab.url);
            
            // Сохраняем ID вкладки для возврата
            const spaceTabId = tab.id;
            
            // Функция скриншотов удалена (была для отладки)
            
            // Сначала всегда пробуем инъектировать скрипт
            try {
                console.log('Injecting content script proactively...');
                await chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    files: ['content_space.js']
                });
                console.log('Content script injected successfully');
                // Ждём немного для инициализации
                await new Promise(resolve => setTimeout(resolve, 1000));
            } catch (injectError) {
                // Скрипт уже может быть загружен, это нормально
                console.log('Script might already be loaded:', injectError.message);
            }
            
            // Теперь отправляем сообщение
            try {
                console.log('Sending request to content script...', new Date().toISOString());
                const response = await new Promise((resolve, reject) => {
                    chrome.tabs.sendMessage(spaceTabId, {
                        type: 'PROCESS_REQUEST',
                        data: request
                    }, (response) => {
                        if (chrome.runtime.lastError) {
                            reject(new Error(chrome.runtime.lastError.message));
                        } else {
                            resolve(response);
                        }
                    });
                });
                console.log('Got response from content script:', response, new Date().toISOString());
                
                // Функция скриншотов удалена (была для отладки)
                
                // Детальное логирование ответа
                if (response) {
                    console.log('Response details:', {
                        id: response.id,
                        hasContent: !!response.content,
                        contentType: typeof response.content,
                        contentLength: response.content ? 
                            (Array.isArray(response.content) ? response.content.length : response.content.length) : 0,
                        hasError: !!response.error,
                        error: response.error
                    });
                    
                    if (response.content) {
                        if (Array.isArray(response.content)) {
                            console.log('Content array:', response.content);
                        } else if (typeof response.content === 'string') {
                            console.log('Content string preview:', response.content.substring(0, 200));
                        }
                    }
                } else {
                    console.log('Response is null or undefined!');
                }
                
                // Отправляем ответ обратно на сервер
                ws.send(JSON.stringify(response));
                console.log('Sent response to server', new Date().toISOString());
                
                // Возвращаем фокус на вкладку с пространством
                await chrome.tabs.update(spaceTabId, { active: true });
                console.log('Returned focus to space tab');
                
            } catch (sendError) {
                console.log('Content script not loaded, injecting it...');
                console.log('Send error details:', sendError);
                
                // Используем полную версию
                const scriptFile = 'content_space.js';
                console.log(`Injecting ${scriptFile} for URL: ${tab.url}`);
                
                try {
                    // Внедряем соответствующий content script
                    await chrome.scripting.executeScript({
                        target: { tabId: tab.id },
                        files: [scriptFile]
                    });
                    
                    console.log(`Successfully injected ${scriptFile}`);
                    
                    // Ждем загрузки и пробуем снова
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    
                    const response = await new Promise((resolve, reject) => {
                        chrome.tabs.sendMessage(spaceTabId, {
                            type: 'PROCESS_REQUEST',
                            data: request
                        }, (response) => {
                            if (chrome.runtime.lastError) {
                                reject(new Error(chrome.runtime.lastError.message));
                            } else {
                                resolve(response);
                            }
                        });
                    });
                    console.log('Got response after script injection:', response);
                    
                    ws.send(JSON.stringify(response));
                    
                    // Возвращаем фокус на вкладку с пространством
                    await chrome.tabs.update(spaceTabId, { active: true });
                    console.log('Returned focus to space tab after retry');
                    
                } catch (retryError) {
                    console.error('Failed after injecting script:', retryError);
                    console.error('Tab URL:', tab.url);
                    console.error('Script file used:', scriptFile);
                    console.error('Retry error details:', {
                        message: retryError.message,
                        stack: retryError.stack
                    });
                    
                    // Функция скриншотов удалена (была для отладки)
                    
                    ws.send(JSON.stringify({
                        id: request.id,
                        error: `Failed to communicate with page: ${retryError.message}`
                    }));
                }
            }
            
            // ВАЖНО: Увеличиваем задержку чтобы избежать 429 ошибок
            await new Promise(resolve => setTimeout(resolve, 3000));
            
        } catch (error) {
            console.error('Error processing request:', error);
            if (request.id) {
                ws.send(JSON.stringify({
                    id: request.id,
                    error: error.message
                }));
            }
        }
    }
    
    isProcessing = false;
    console.log('[QUEUE] Finished processing. isProcessing set to false. Remaining queue length:', messageQueue.length);
    
    // Если в очереди есть еще сообщения, обработаем их
    if (messageQueue.length > 0) {
        console.log('[QUEUE] Queue has more messages, calling processQueue again...');
        processQueue();
    }
}

// Функция загрузки куки с сервера
async function loadCookiesFromServer() {
    try {
        console.log('Loading cookies from server...');
        const response = await fetch('http://localhost:3002/cookies/load');
        const data = await response.json();
        console.log('Server response:', data);
        
        if (data.cookies && data.cookies.length > 0) {
            console.log(`Loading ${data.cookies.length} cookies...`);
            
            for (const cookie of data.cookies) {
                try {
                    // Преобразуем куки в формат Chrome
                    const chromeCookie = {
                        url: `${cookie.secure ? 'https' : 'http'}://${cookie.domain}${cookie.path}`,
                        name: cookie.name,
                        value: cookie.value,
                        domain: cookie.domain,
                        path: cookie.path,
                        secure: cookie.secure || false,
                        httpOnly: cookie.httpOnly || false,
                        sameSite: cookie.sameSite || 'lax'
                    };
                    
                    // Добавляем expirationDate если есть
                    if (cookie.expirationDate) {
                        chromeCookie.expirationDate = cookie.expirationDate;
                    }
                    
                    // Устанавливаем куки
                    await chrome.cookies.set(chromeCookie);
                    console.log(`✓ Cookie set: ${cookie.name} for ${cookie.domain}`);
                } catch (err) {
                    console.error(`Failed to set cookie ${cookie.name}:`, err);
                }
            }
            
            console.log('Cookies loaded successfully');
            
            // Перезагружаем вкладку Perplexity после загрузки куки
            const tabs = await chrome.tabs.query({ url: '*://*.perplexity.ai/*' });
            if (tabs.length > 0) {
                chrome.tabs.reload(tabs[0].id);
                console.log('Perplexity tab reloaded after cookie import');
            }
        } else {
            console.log('No cookies to load');
        }
    } catch (err) {
        console.error('Failed to load cookies:', err);
    }
}

// Агрессивное подключение при запуске
console.log('Extension starting, attempting to connect...');
connectWebSocket();

// Повторяем попытку подключения каждые 3 секунды
setInterval(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.log('WebSocket not connected, attempting to connect...');
        connectWebSocket();
    } else {
        console.log('WebSocket is connected');
    }
}, 3000);

// Переподключаемся при обновлении вкладок с пространством
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url?.includes('perplexity.ai/spaces/')) {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            connectWebSocket();
        }
    }
});

// Следим за закрытием вкладок с пространством
chrome.tabs.onRemoved.addListener(async (tabId) => {
    const spaceTabs = await chrome.tabs.query({ url: 'https://www.perplexity.ai/spaces/*' });
    if (spaceTabs.length === 0) {
        console.log('No space tabs left, clearing queue');
        messageQueue = [];
    }
});