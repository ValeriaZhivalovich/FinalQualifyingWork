import flet as ft
from news_analyzer.utils.env_persister import persist_settings_to_env


class SettingsPage:
    """Страница настроек"""

    def __init__(self, repository=None, ai_agent=None):
        self.repository = repository
        self.ai_agent = ai_agent
        self.page = None
        self.container = None

        self.host_field = ft.TextField(label="Ollama Host", value="http://localhost:11434", width=300)
        self.model_field = ft.TextField(label="Model", value="mistral:7b", width=300)
        self.interval_field = ft.TextField(label="Интервал парсинга (мин)", value="30", width=300)
        self.theme_switch = ft.Switch(label="Тёмная тема", value=True)
        self.auto_update_switch = ft.Switch(label="Автообновление", value=False)
        self.stats_text = ft.Text("", size=14, color=ft.Colors.GREY)

    def build(self, page=None) -> ft.Container:
        """Build the settings page UI"""
        self.page = page
        self._load_stats()

        def on_test_connection(e):
            self._test_ollama()

        def on_save(e):
            self._save_settings()

        def on_toggle_theme(e):
            if self.page:
                self.page.theme_mode = ft.ThemeMode.DARK if self.theme_switch.value else ft.ThemeMode.LIGHT
                self.page.update()

        self.theme_switch.on_change = on_toggle_theme

        content = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Настройки", size=26, weight=ft.FontWeight.BOLD),
                        ft.Text("Конфигурация приложения", size=14, color=ft.Colors.GREY),
                    ]),
                    padding=20,
                ),
                ft.Divider(),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Ollama", weight=ft.FontWeight.BOLD, size=18),
                        self.host_field,
                        self.model_field,
                        ft.ElevatedButton("Проверить подключение", icon=ft.Icons.LINK, on_click=on_test_connection),
                        ft.Container(height=20),
                        ft.Text("Парсинг", weight=ft.FontWeight.BOLD, size=18),
                        self.interval_field,
                        ft.Container(height=20),
                        ft.Text("Интерфейс", weight=ft.FontWeight.BOLD, size=18),
                        self.theme_switch,
                        self.auto_update_switch,
                        ft.Container(height=20),
                        ft.Text("Статистика", weight=ft.FontWeight.BOLD, size=18),
                        self.stats_text,
                        ft.Container(height=20),
                        ft.ElevatedButton("Сохранить", icon=ft.Icons.SAVE, on_click=on_save),
                    ], spacing=10),
                    padding=20,
                    width=400,
                ),
            ]),
            expand=True
        )

        self.container = content
        return content

    def _load_stats(self):
        """Load statistics"""
        if not self.repository:
            self.stats_text.value = "БД не подключена"
            return
        try:
            articles = self.repository.get_articles(limit=999999)
            categories = self.repository.get_categories()
            sources = self.repository.get_sources()
            read_count = sum(1 for a in articles if a.is_read)
            self.stats_text.value = (
                f"Всего новостей: {len(articles)}\n"
                f"Категорий: {len(categories)}\n"
                f"Источников: {len(sources)}\n"
                f"Прочитано: {read_count}, Непрочитано: {len(articles) - read_count}"
            )
        except Exception as e:
            self.stats_text.value = f"Ошибка: {e}"

    def _test_ollama(self):
        """Test Ollama connection"""
        if not self.page:
            return

        host = self.host_field.value.rstrip('/')
        model = self.model_field.value

        if self.ai_agent:
            self.ai_agent.host = host
            self.ai_agent.model_name = model
            self.ai_agent.api_url = f"{host}/api/generate"

            connected = self.ai_agent.validate_connection()

            if connected:
                self.page.show_dialog(ft.SnackBar(ft.Text(f"Ollama подключён! Модель: {model}")))
            else:
                self.page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось подключиться к Ollama ({host})")))
            self.page.update()
        else:
            self.page.show_dialog(ft.SnackBar(ft.Text("ИИ-агент не инициализирован")))

    def _save_settings(self):
        """Save settings"""
        if not self.page:
            return

        host = self.host_field.value
        model = self.model_field.value
        interval = self.interval_field.value
        theme = 'dark' if self.theme_switch.value else 'light'

        persist_settings_to_env(host, model, interval, theme)

        self.page.theme_mode = ft.ThemeMode.DARK if self.theme_switch.value else ft.ThemeMode.LIGHT

        if self.ai_agent:
            self.ai_agent.host = host.rstrip('/')
            self.ai_agent.model_name = model
            self.ai_agent.api_url = f"{host.rstrip('/')}/api/generate"

        self.page.show_dialog(ft.SnackBar(ft.Text("Настройки сохранены")))
        self._load_stats()
        self.page.update()
