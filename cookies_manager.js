const fs = require('fs').promises;
const path = require('path');

class CookiesManager {
    constructor() {
        this.cookiesFile = path.join(__dirname, 'cookies.json');
        this.cookies = [];
        this.loadCookies();
    }

    async loadCookies() {
        try {
            const data = await fs.readFile(this.cookiesFile, 'utf8');
            this.cookies = JSON.parse(data);
            console.log(`✅ Загружено ${this.cookies.length} cookies`);
        } catch (error) {
            console.error('⚠️ Не удалось загрузить cookies:', error.message);
            this.cookies = [];
        }
    }

    async saveCookies(cookies) {
        try {
            this.cookies = cookies;
            await fs.writeFile(this.cookiesFile, JSON.stringify(cookies, null, 2));
            console.log(`✅ Сохранено ${cookies.length} cookies`);
        } catch (error) {
            console.error('❌ Ошибка сохранения cookies:', error);
        }
    }

    getCookies() {
        return this.cookies;
    }

    async updateCookies(newCookies) {
        if (!Array.isArray(newCookies)) return;
        
        // Объединяем с существующими cookies
        const cookieMap = new Map();
        
        // Сначала добавляем старые
        this.cookies.forEach(cookie => {
            const key = `${cookie.domain}-${cookie.name}`;
            cookieMap.set(key, cookie);
        });
        
        // Перезаписываем новыми
        newCookies.forEach(cookie => {
            const key = `${cookie.domain}-${cookie.name}`;
            cookieMap.set(key, cookie);
        });
        
        this.cookies = Array.from(cookieMap.values());
        await this.saveCookies(this.cookies);
    }

    setupAutoSave() {
        // Автосохранение каждые 5 минут
        setInterval(async () => {
            if (this.cookies.length > 0) {
                await this.saveCookies(this.cookies);
            }
        }, 5 * 60 * 1000);
    }
}

module.exports = CookiesManager;