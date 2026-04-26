console.log('Perplexity Space content script loaded! SIMPLIFIED VERSION');

// Space ID будет передаваться динамически или использоваться из URL
const SPACE_ID = window.location.pathname.split('/spaces/')[1] || 'crypto-asistant-T51ZY9NXQUunuH1GpXVkzg';
const TARGET_SPACE_URL = `https://www.perplexity.ai/spaces/${SPACE_ID}`;

// Таймаут для операций
const OPERATION_TIMEOUT = 60000; // 60 секунд

// Функция с таймаутом
async function withTimeout(promise, timeoutMs = OPERATION_TIMEOUT) {
    const timeout = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Operation timeout')), timeoutMs)
    );
    return Promise.race([promise, timeout]);
}

// Основная функция обработки запроса
async function handleRequest(request) {
    console.log('[SPACE] Handling request:', request.id);
    
    // Сохраняем оригинальный ID до распаковки
    // ID может быть в request.id (прямой запрос) или в request.data.id (обернутый от background.js)
    const requestId = request.data?.id || request.id || 'unknown';
    console.log('[SPACE] Request ID:', requestId);
    
    try {
        
        // 1. Проверяем, в нужном ли мы пространстве
        if (!window.location.href.includes(SPACE_ID)) {
            console.log('[SPACE] Not in target space, redirecting...');
            window.location.href = TARGET_SPACE_URL;
            return { id: requestId, error: 'REDIRECTING_TO_SPACE' };
        }
        
        // 2. Ждем загрузки страницы
        await waitForPageReady();
        
        // 3. Находим поле ввода с несколькими попытками
        let input = null;
        let attempts = 0;
        const maxAttempts = 5;
        
        while (!input && attempts < maxAttempts) {
            input = findInputField();
            if (!input) {
                console.log(`[SPACE] Input not found, attempt ${attempts + 1}/${maxAttempts}`);
                await new Promise(resolve => setTimeout(resolve, 1000));
                attempts++;
            }
        }
        
        if (!input) {
            // Дополнительная диагностика перед ошибкой
            console.log('[SPACE] Failed to find input after all attempts');
            console.log('[SPACE] Page title:', document.title);
            console.log('[SPACE] Body classes:', document.body.className);
            
            // Логируем все textarea для отладки
            const allTextareas = document.querySelectorAll('textarea');
            console.log('[SPACE] Total textareas on page:', allTextareas.length);
            allTextareas.forEach((ta, i) => {
                const rect = ta.getBoundingClientRect();
                console.log(`[SPACE] Textarea ${i} debug info:`, {
                    placeholder: ta.placeholder,
                    visible: ta.offsetHeight > 0 && ta.offsetWidth > 0,
                    className: ta.className,
                    id: ta.id,
                    name: ta.name,
                    ariaLabel: ta.getAttribute('aria-label'),
                    dataTestId: ta.getAttribute('data-testid'),
                    position: `top: ${rect.top}, bottom: ${rect.bottom}`,
                    nearBottom: rect.top > window.innerHeight * 0.5,
                    parent: ta.parentElement?.tagName,
                    parentClass: ta.parentElement?.className
                });
            });
            
            console.log('[SPACE] Returning SKIP - no suitable input found');
            return {
                id: requestId,
                content: [{
                    type: 'text',
                    text: 'SKIP'
                }]
            };
        }
        
        // 4. Извлекаем текст из content (может быть строкой или массивом)
        // Поддерживаем разные форматы запроса
        
        // Распаковываем данные если они обернуты (background.js отправляет в data)
        // background.js отправляет: {type: 'PROCESS_REQUEST', data: originalRequest}
        // где originalRequest = {id, type, messages, max_tokens}
        let actualRequest = request.data || request;
        
        console.log('[CONTENT] Processing request structure:', {
            requestType: request.type,
            hasRequestData: !!request.data,
            actualRequestKeys: Object.keys(actualRequest || {}),
            hasMessages: !!(actualRequest && actualRequest.messages),
            messagesLength: actualRequest && actualRequest.messages ? actualRequest.messages.length : 0,
            fullRequest: request
        });
        
        let messageContent;
        if (actualRequest && actualRequest.messages && actualRequest.messages.length > 0) {
            console.log('[CONTENT] Found messages array with', actualRequest.messages.length, 'messages');
            console.log('[CONTENT] First message:', actualRequest.messages[0]);
            messageContent = actualRequest.messages[0].content;
        } else if (actualRequest && actualRequest.data && actualRequest.data.message) {
            // Простой формат с прямым сообщением
            console.log('[CONTENT] Found simple message format');
            messageContent = actualRequest.data.message;
        } else if (actualRequest && actualRequest.message) {
            // Альтернативный формат
            console.log('[CONTENT] Found alternative message format');
            messageContent = actualRequest.message;
        } else {
            console.error('[CONTENT] No message found in request:', {
                request: request,
                actualRequest: actualRequest,
                requestKeys: Object.keys(request || {}),
                actualRequestKeys: Object.keys(actualRequest || {}),
                messages: actualRequest?.messages,
                messagesType: typeof actualRequest?.messages,
                messagesArray: Array.isArray(actualRequest?.messages)
            });
            throw new Error('No message content found in request');
        }
        
        let messageText = messageContent;
        let imageBlocks = [];
        
        // Если content - это массив (с изображениями), извлекаем текст и изображения
        if (Array.isArray(messageContent)) {
            console.log('[SPACE] Content is array with', messageContent.length, 'items');
            // Ищем текстовый блок
            const textBlock = messageContent.find(item => item.type === 'text');
            messageText = textBlock ? textBlock.text : '';
            
            // Извлекаем изображения
            imageBlocks = messageContent.filter(item => item.type === 'image_url');
            if (imageBlocks.length > 0) {
                console.log('[SPACE] Message contains', imageBlocks.length, 'images');
            }
        }
        
        // Если есть изображения, добавляем уведомление к тексту
        let finalText = messageText;
        if (imageBlocks.length > 0) {
            console.log('[SPACE] Processing images before sending message...');
            const imageNotice = await attachImages(input, imageBlocks);
            finalText = messageText + imageNotice;
        }
        
        // Вставляем текст и отправляем
        await sendMessage(input, finalText);
        
        // 5. Ждем завершения генерации и собираем ответ
        const response = await waitAndCollectResponse();
        
        // 6. Возвращаемся в пространство если нужно
        if (!window.location.href.includes('/spaces/')) {
            console.log('[SPACE] Returning to space...');
            setTimeout(() => {
                window.location.href = TARGET_SPACE_URL;
            }, 1000);
        }
        
        // 7. Возвращаем результат
        return {
            id: requestId,
            content: [{
                type: 'text',
                text: response
            }]
        };
        
    } catch (error) {
        console.error('[SPACE] Error:', error);
        console.error('[SPACE] Error stack:', error.stack);
        
        // requestId определен вне try блока, так что доступен здесь
        
        // Если не нашли поле ввода - возвращаем SKIP вместо ERROR
        if (error.message && error.message.includes('Input field not found')) {
            console.log('[SPACE] Input field not found - returning SKIP');
            return {
                id: requestId,
                content: [{
                    type: 'text',
                    text: 'SKIP'
                }]
            };
        }
        
        return {
            id: requestId,
            content: [{
                type: 'text',
                text: 'ERROR: ' + (error.message || 'Unknown error')
            }]
        };
    }
}

// Ожидание готовности страницы
async function waitForPageReady() {
    console.log('[SPACE] Waiting for page ready...');
    
    // Ждем загрузки DOM
    if (document.readyState !== 'complete') {
        await new Promise(resolve => {
            window.addEventListener('load', resolve);
        });
    }
    
    // Даем время на инициализацию React
    await new Promise(resolve => setTimeout(resolve, 1000));
}

// Проверка, что элемент подходит для ввода
function isValidInput(element) {
    if (!element) return false;
    
    // Проверка видимости
    const rect = element.getBoundingClientRect();
    const isVisible = rect.width > 0 && rect.height > 0 && 
                     element.offsetHeight > 0 && element.offsetWidth > 0 &&
                     window.getComputedStyle(element).display !== 'none' &&
                     window.getComputedStyle(element).visibility !== 'hidden';
    
    if (!isVisible) return false;
    
    // Проверка, что не disabled
    if (element.disabled || element.readOnly) return false;
    
    // Проверка, что это не поиск и не навигация
    const placeholder = (element.placeholder || element.getAttribute('placeholder') || '').toLowerCase();
    const ariaLabel = (element.getAttribute('aria-label') || '').toLowerCase();
    const className = (element.className || '').toLowerCase();
    const id = (element.id || '').toLowerCase();
    
    // Если это ask-input - всегда валидно
    if (id === 'ask-input') return true;
    
    // Исключаем поисковые поля и навигацию
    if (placeholder.includes('search') || 
        ariaLabel.includes('search') ||
        placeholder.includes('find') ||
        className.includes('search')) return false;
    
    return true;
}

// Поиск поля ввода
function findInputField() {
    console.log('[SPACE] Looking for input field...');
    console.log('[SPACE] Current URL:', window.location.href);
    
    // Стратегия 1: Сначала ищем по ID (самый точный селектор) - может быть любой элемент
    const askInput = document.getElementById('ask-input') || 
                     document.querySelector('#ask-input') || 
                     document.querySelector('[id="ask-input"]');
    if (askInput) {
        console.log('[SPACE] Found #ask-input directly, type:', askInput.tagName);
        return askInput;
    }
    
    // Стратегия 2: Поиск по специфичным селекторам для Perplexity Spaces
    const specificSelectors = [
        // Основное поле ввода в Spaces
        'div[data-radix-collection-item] textarea',
        'main textarea[placeholder*="message" i]',
        'main textarea[placeholder*="ask" i]',
        'main textarea[placeholder*="type" i]',
        // Поле в нижней части экрана
        'div[class*="bottom"] textarea',
        'div[class*="footer"] textarea',
        // Исключаем поисковые поля
        'main form textarea:not([placeholder*="search" i])',
        'textarea[data-testid="space-input"]',
        'textarea.w-full.resize-none:not([placeholder*="search" i])'
    ];
    
    // Сначала пробуем специфичные селекторы
    for (const selector of specificSelectors) {
        const element = document.querySelector(selector);
        if (element && isValidInput(element)) {
            console.log('[SPACE] Found input with specific selector:', selector);
            return element;
        }
    }
    
    // Стратегия 2: Ищем все textarea и input элементы
    const allInputs = document.querySelectorAll('textarea, input[type="text"], input:not([type])');
    console.log('[SPACE] Found', allInputs.length, 'input/textarea elements');
    
    // Фильтруем и сортируем по приоритету
    const validTextareas = Array.from(allInputs)
        .filter(elem => isValidInput(elem))
        .sort((a, b) => {
            const aRect = a.getBoundingClientRect();
            const bRect = b.getBoundingClientRect();
            const windowHeight = window.innerHeight;
            
            // Приоритет 1: Поле в нижней части экрана
            const aNearBottom = aRect.top > windowHeight * 0.6;
            const bNearBottom = bRect.top > windowHeight * 0.6;
            if (aNearBottom !== bNearBottom) return aNearBottom ? -1 : 1;
            
            // Приоритет 2: С placeholder содержащим "message" или "ask"
            const aPlaceholder = (a.placeholder || '').toLowerCase();
            const bPlaceholder = (b.placeholder || '').toLowerCase();
            const aGoodPlaceholder = aPlaceholder.includes('message') || aPlaceholder.includes('ask') || aPlaceholder.includes('type');
            const bGoodPlaceholder = bPlaceholder.includes('message') || bPlaceholder.includes('ask') || bPlaceholder.includes('type');
            if (aGoodPlaceholder !== bGoodPlaceholder) return aGoodPlaceholder ? -1 : 1;
            
            // Приоритет 3: Видимая и большая
            const aSize = a.offsetWidth * a.offsetHeight;
            const bSize = b.offsetWidth * b.offsetHeight;
            if (aSize !== bSize) return bSize - aSize;
            
            return 0;
        });
    
    if (validTextareas.length > 0) {
        console.log('[SPACE] Using best textarea from', validTextareas.length, 'valid options');
        return validTextareas[0];
    }
    
    // Стратегия 3: Поиск contenteditable
    const editableSelectors = [
        '[contenteditable="true"]',
        '[role="textbox"]',
        'div[data-placeholder]'
    ];
    
    for (const selector of editableSelectors) {
        const element = document.querySelector(selector);
        if (element && isValidInput(element)) {
            console.log('[SPACE] Found contenteditable element:', selector);
            return element;
        }
    }
    
    console.log('[SPACE] No suitable input field found');
    return null;
}

// Функция для прикрепления изображений
async function attachImages(input, imageBlocks) {
    console.log('[SPACE] Attempting to attach', imageBlocks.length, 'images via paste event');
    
    let successCount = 0;
    
    for (let i = 0; i < imageBlocks.length; i++) {
        const imageBlock = imageBlocks[i];
        const imageUrl = imageBlock.image_url?.url;
        
        if (!imageUrl) {
            console.log('[SPACE] Skipping image', i + 1, '- no URL');
            continue;
        }
        
        console.log('[SPACE] Processing image', i + 1, '/', imageBlocks.length);
        
        try {
            // Конвертируем base64 в blob
            const base64 = imageUrl.split(',')[1];
            const byteCharacters = atob(base64);
            const byteNumbers = new Array(byteCharacters.length);
            
            for (let j = 0; j < byteCharacters.length; j++) {
                byteNumbers[j] = byteCharacters.charCodeAt(j);
            }
            
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'image/jpeg' });
            
            // Создаем File объект
            const file = new File([blob], `image_${i + 1}.jpg`, { type: 'image/jpeg' });
            
            // Создаем DataTransfer для эмуляции вставки
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            
            // Создаем событие paste
            const pasteEvent = new ClipboardEvent('paste', {
                clipboardData: dataTransfer,
                bubbles: true,
                cancelable: true
            });
            
            // Фокусируемся на поле ввода
            input.focus();
            input.click();
            
            // Небольшая задержка
            await new Promise(resolve => setTimeout(resolve, 100));
            
            // Отправляем paste event
            const result = input.dispatchEvent(pasteEvent);
            console.log('[SPACE] Paste event dispatched, default prevented:', !result);
            
            // Ждем обработки вставки
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // Проверяем успешность
            const uploadedImages = document.querySelectorAll('[data-testid*="image"], [class*="upload"], img[src*="blob:"], img[src*="data:"]');
            if (uploadedImages.length > successCount) {
                successCount++;
                console.log('[SPACE] Image', i + 1, 'successfully pasted');
            } else {
                console.log('[SPACE] Image', i + 1, 'paste may have failed');
            }
            
        } catch (error) {
            console.error('[SPACE] Error attaching image', i + 1, ':', error);
        }
    }
    
    if (successCount > 0) {
        console.log('[SPACE] Successfully attached', successCount, 'of', imageBlocks.length, 'images');
        return ''; // Не добавляем текст если изображения загружены
    } else {
        console.log('[SPACE] Failed to attach images');
        return `\n\n[Не удалось прикрепить ${imageBlocks.length} изображение(й)]`;
    }
}

// Отправка сообщения
async function sendMessage(input, text) {
    console.log('[SPACE] Sending message to input type:', input.tagName, 'id:', input.id);
    
    // Агрессивная активация поля
    input.scrollIntoView({ behavior: 'smooth', block: 'center' });
    await new Promise(resolve => setTimeout(resolve, 500));
    
    input.focus();
    input.click();
    await new Promise(resolve => setTimeout(resolve, 200));
    
    // Еще раз для надежности
    input.focus();
    
    // Симулируем клик мышью
    const clickEvent = new MouseEvent('click', {
        view: window,
        bubbles: true,
        cancelable: true
    });
    input.dispatchEvent(clickEvent);
    await new Promise(resolve => setTimeout(resolve, 200));
    
    // Обрабатываем по-разному для textarea, input и других элементов
    if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {
        // Очищаем поле
        input.value = '';
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Для textarea и input используем value
        input.value = text;
        
        // Триггерим события для React
        const descriptor = input.tagName === 'TEXTAREA' 
            ? Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")
            : Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
        
        if (descriptor && descriptor.set) {
            descriptor.set.call(input, text);
        }
        
        const inputEvent = new Event('input', { bubbles: true });
        input.dispatchEvent(inputEvent);
        
        // Также пробуем change событие
        input.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
        // Для contenteditable элементов
        input.textContent = '';
        input.innerHTML = '';
        document.execCommand('insertText', false, text);
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    
    // Небольшая задержка
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Симулируем нажатие Enter с полным набором свойств для React
    console.log('[SPACE] Pressing Enter...');
    
    // Для React нужно правильное событие с nativeEvent
    const enterEvent = new KeyboardEvent('keydown', {
        key: 'Enter',
        code: 'Enter',
        keyCode: 13,
        charCode: 13,
        which: 13,
        bubbles: true,
        cancelable: true,
        composed: true,
        isTrusted: false
    });
    
    // React может проверять эти свойства
    Object.defineProperty(enterEvent, 'target', {
        value: input,
        enumerable: true
    });
    
    const result = input.dispatchEvent(enterEvent);
    console.log('[SPACE] Enter event dispatched, prevented:', !result);
    
    // Если keydown не сработал, пробуем keypress и keyup
    if (result) {
        input.dispatchEvent(new KeyboardEvent('keypress', {
            key: 'Enter',
            code: 'Enter',
            keyCode: 13,
            charCode: 13,
            which: 13,
            bubbles: true
        }));
        
        input.dispatchEvent(new KeyboardEvent('keyup', {
            key: 'Enter',
            code: 'Enter',
            keyCode: 13,
            which: 13,
            bubbles: true
        }));
    }
    
    // Ждем начала отправки
    await new Promise(resolve => setTimeout(resolve, 500));
}

// Поиск кнопки отправки
function findSendButton() {
    // Ищем кнопку рядом с полем ввода
    const buttons = document.querySelectorAll('button');
    
    for (const button of buttons) {
        // Проверяем видимость
        if (button.offsetHeight === 0) continue;
        
        // Проверяем различные признаки кнопки отправки
        const ariaLabel = button.getAttribute('aria-label')?.toLowerCase() || '';
        const title = button.getAttribute('title')?.toLowerCase() || '';
        const innerHTML = button.innerHTML.toLowerCase();
        
        if (ariaLabel.includes('send') || 
            ariaLabel.includes('submit') ||
            title.includes('send') ||
            title.includes('submit') ||
            innerHTML.includes('send') ||
            innerHTML.includes('submit')) {
            console.log('[SPACE] Found send button by text');
            return button;
        }
        
        // Проверяем наличие SVG иконки (обычно стрелка)
        const svg = button.querySelector('svg');
        if (svg && button.querySelectorAll('*').length < 10) {
            console.log('[SPACE] Found send button by SVG');
            return button;
        }
    }
    
    console.log('[SPACE] Send button not found');
    return null;
}

// Ожидание и сбор ответа
async function waitAndCollectResponse() {
    console.log('[SPACE] Waiting for response...');
    
    const startTime = Date.now();
    const maxWait = 90000; // 90 секунд
    
    // Ждем начала генерации
    let generationStarted = false;
    while (!generationStarted && Date.now() - startTime < 10000) {
        const indicators = document.querySelectorAll(
            '[class*="loading"], [class*="generating"], ' +
            '[class*="skeleton"], [class*="pulse"], ' +
            '.animate-pulse, [aria-busy="true"]'
        );
        
        if (indicators.length > 0) {
            generationStarted = true;
            console.log('[SPACE] Generation started');
            break;
        }
        
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    // Ждем завершения генерации
    let lastText = '';
    let stableCount = 0;
    
    while (Date.now() - startTime < maxWait) {
        const currentText = extractLatestResponse();
        
        if (currentText === lastText && currentText) {
            stableCount++;
            if (stableCount >= 10) { // Текст стабилен 1 секунду
                console.log('[SPACE] Response stabilized');
                break;
            }
        } else {
            stableCount = 0;
        }
        
        lastText = currentText;
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    // Финальный сбор ответа
    const finalResponse = extractLatestResponse();
    console.log('[SPACE] Final response length:', finalResponse.length);
    
    return finalResponse || 'NO_RESPONSE';
}

// Извлечение последнего ответа
function extractLatestResponse() {
    // Ищем элементы с ответом
    const selectors = [
        '[class*="prose"]',
        '[class*="markdown"]',
        '[class*="response"]',
        '[class*="answer"]',
        'div[id^="markdown-content"]'
    ];
    
    let latestResponse = '';
    
    for (const selector of selectors) {
        const elements = document.querySelectorAll(selector);
        for (let i = elements.length - 1; i >= 0; i--) {
            const element = elements[i];
            const text = element.innerText?.trim();
            
            // Пропускаем пустые или системные элементы
            if (!text || text.length < 2) continue;
            if (element.contentEditable === 'true') continue;
            if (text.includes('Ask anything') || text.includes('Спросите что угодно')) continue;
            
            // Нашли ответ
            latestResponse = text;
            break;
        }
        
        if (latestResponse) break;
    }
    
    return latestResponse;
}

// Слушаем сообщения от background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log('[SPACE] Received message:', request);
    
    // Асинхронная обработка
    handleRequest(request).then(response => {
        console.log('[SPACE] Sending response:', response);
        sendResponse(response);
    });
    
    return true; // Для асинхронного ответа
});

console.log('[SPACE] Content script ready');