const fs = require('fs');
const path = require('path');
const util = require('util');

// Создаем директорию для логов
const logsDir = path.join(__dirname, 'logs');
if (!fs.existsSync(logsDir)) {
    fs.mkdirSync(logsDir, { recursive: true });
}

// Настройки ротации
const MAX_LOG_SIZE = 50 * 1024 * 1024; // 50MB
const MAX_LOG_FILES = 5; // Максимум 5 файлов каждого типа

// Файлы логов
const mainLogFile = path.join(logsDir, 'server.log');
const errorLogFile = path.join(logsDir, 'server_errors.log');

// Функция для ротации логов
function rotateLogIfNeeded(logPath, logType) {
    try {
        if (fs.existsSync(logPath)) {
            const stats = fs.statSync(logPath);
            if (stats.size > MAX_LOG_SIZE) {
                const timestamp = new Date().toISOString().replace(/:/g, '-').replace(/\./g, '-');
                const rotatedPath = path.join(logsDir, `${logType}_${timestamp}.log`);
                
                // Переименовываем текущий файл
                fs.renameSync(logPath, rotatedPath);
                
                // Удаляем старые файлы если их слишком много
                const files = fs.readdirSync(logsDir)
                    .filter(f => f.startsWith(logType + '_') && f.endsWith('.log'))
                    .map(f => ({
                        name: f,
                        path: path.join(logsDir, f),
                        time: fs.statSync(path.join(logsDir, f)).mtime
                    }))
                    .sort((a, b) => b.time - a.time);
                
                // Удаляем старые файлы, оставляя только MAX_LOG_FILES
                if (files.length > MAX_LOG_FILES) {
                    files.slice(MAX_LOG_FILES).forEach(file => {
                        fs.unlinkSync(file.path);
                        console.log(`[LOG ROTATION] Deleted old log file: ${file.name}`);
                    });
                }
                
                return true; // Ротация выполнена
            }
        }
    } catch (error) {
        // Игнорируем ошибки ротации
    }
    return false;
}

// Потоки для записи в файлы
let mainLogStream = fs.createWriteStream(mainLogFile, { flags: 'a' });
let errorLogStream = fs.createWriteStream(errorLogFile, { flags: 'a' });

// Форматирование времени
function formatTime() {
    return new Date().toISOString().replace('T', ' ').substr(0, 19);
}

// Оригинальные методы console
const originalLog = console.log;
const originalError = console.error;
const originalWarn = console.warn;

// Флаг для важных сообщений
const IMPORTANT_MESSAGES = [
    'Perplexity browser bridge running',
    'Extension connected',
    'Extension disconnected',
    'Server stopped',
    'CRITICAL',
    'ERROR'
];

// Проверка важности сообщения
function isImportant(args) {
    const message = util.format(...args);
    return IMPORTANT_MESSAGES.some(msg => message.includes(msg));
}

// Переопределяем console.log
console.log = function(...args) {
    const timestamp = formatTime();
    const message = util.format(...args);
    const logLine = `[${timestamp}] INFO: ${message}\n`;
    
    // Проверяем ротацию перед записью
    if (rotateLogIfNeeded(mainLogFile, 'server')) {
        // Пересоздаем поток после ротации
        mainLogStream.end();
        mainLogStream = fs.createWriteStream(mainLogFile, { flags: 'a' });
    }
    
    // Всегда пишем в файл
    mainLogStream.write(logLine);
    
    // В консоль всегда для важных сообщений и сервера
    if (isImportant(args) || message.includes('running on port') || message.includes('WebSocket')) {
        originalLog(message);
    }
};

// Переопределяем console.error
console.error = function(...args) {
    const timestamp = formatTime();
    const message = util.format(...args);
    const logLine = `[${timestamp}] ERROR: ${message}\n`;
    
    // Проверяем ротацию для обоих файлов
    if (rotateLogIfNeeded(mainLogFile, 'server')) {
        mainLogStream.end();
        mainLogStream = fs.createWriteStream(mainLogFile, { flags: 'a' });
    }
    if (rotateLogIfNeeded(errorLogFile, 'server_errors')) {
        errorLogStream.end();
        errorLogStream = fs.createWriteStream(errorLogFile, { flags: 'a' });
    }
    
    // Пишем в оба файла
    mainLogStream.write(logLine);
    errorLogStream.write(logLine);
    
    // Ошибки всегда в консоль
    originalError(`❌ ${message}`);
};

// Переопределяем console.warn
console.warn = function(...args) {
    const timestamp = formatTime();
    const message = util.format(...args);
    const logLine = `[${timestamp}] WARN: ${message}\n`;
    
    // Только в файл
    mainLogStream.write(logLine);
};

// Специальный метод для важных сообщений
console.important = function(...args) {
    const timestamp = formatTime();
    const message = util.format(...args);
    const logLine = `[${timestamp}] IMPORTANT: ${message}\n`;
    
    mainLogStream.write(logLine);
    originalLog(`🚀 ${message}`);
};

// Обработка необработанных ошибок
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
    process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// При завершении процесса
process.on('exit', () => {
    mainLogStream.end();
    errorLogStream.end();
});

// Функция для очистки старых логов
function cleanOldLogs() {
    const MAX_AGE_DAYS = 7; // Удаляем логи старше 7 дней
    const now = Date.now();
    const maxAge = MAX_AGE_DAYS * 24 * 60 * 60 * 1000;
    
    try {
        const files = fs.readdirSync(logsDir);
        files.forEach(file => {
            if (file.endsWith('.log') && file !== 'server.log' && file !== 'server_errors.log') {
                const filePath = path.join(logsDir, file);
                const stats = fs.statSync(filePath);
                if (now - stats.mtime.getTime() > maxAge) {
                    fs.unlinkSync(filePath);
                    console.log(`[LOG CLEANUP] Deleted old log file: ${file}`);
                }
            }
        });
    } catch (error) {
        // Игнорируем ошибки очистки
    }
}

// Очищаем старые логи при запуске
cleanOldLogs();

// Планируем очистку каждые 24 часа
setInterval(cleanOldLogs, 24 * 60 * 60 * 1000);

console.log('Logger initialized with rotation support');
console.log(`Log directory: ${logsDir}`);
console.log(`Max log size: ${MAX_LOG_SIZE / 1024 / 1024}MB`);
console.log(`Max log files: ${MAX_LOG_FILES} per type`);

module.exports = {
    log: console.log,
    error: console.error,
    warn: console.warn,
    important: console.important
};