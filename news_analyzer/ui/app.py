import flet as ft
import threading
from typing import List, Dict, Any
from news_analyzer.db.repository import DatabaseRepository
from news_analyzer.pipeline.orchestrator import PipelineOrchestrator
from news_analyzer.ui.pages.feed_page import FeedPage
from news_analyzer.ui.pages.sources_page import SourcesPage
from news_analyzer.ui.pages.settings_page import SettingsPage


class NewsAnalyzerApp:
    """Главное приложение News Analyzer"""

    def __init__(self, orchestrator: PipelineOrchestrator = None, repository: DatabaseRepository = None):
        self.orchestrator = orchestrator
        self.repository = repository
        self.page = None
        self.current_page_index = 0
        self.auto_update_enabled = False
        self.rss_url_field = None

    def main(self, page: ft.Page):
        """Главная функция приложения"""
        self.page = page
        page.title = "News Analyzer"
        page.theme_mode = ft.ThemeMode.DARK
        page.window.width = 1200
        page.window.height = 800

        page.on_disconnect = self.on_close

        self.navigation_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=200,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.FORMAT_LIST_BULLETED,
                    selected_icon=ft.Icons.FORMAT_LIST_BULLETED,
                    label="Лента"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.RSS_FEED,
                    selected_icon=ft.Icons.RSS_FEED,
                    label="Источники"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS,
                    selected_icon=ft.Icons.SETTINGS,
                    label="Настройки"
                ),
            ],
            on_change=self.on_navigation_change
        )

        # Интеграция UI-страниц
        self.feed_page = FeedPage(repository=self.repository, orchestrator=self.orchestrator)
        self.sources_page = SourcesPage(repository=self.repository, orchestrator=self.orchestrator)
        self.settings_page = SettingsPage(repository=self.repository, ai_agent=self.orchestrator.ai_agent if self.orchestrator else None) if self.orchestrator else SettingsPage()

        try:
            self.feed_page.set_refresh_callback(lambda: page.update())
        except Exception:
            pass
        self.page_content = ft.Container(
            content=self.feed_page.build(page=self.page),
            expand=True
        )

        page.add(
            ft.Row([
                self.navigation_rail,
                ft.VerticalDivider(width=1),
                self.page_content
            ], expand=True)
        )

    def on_navigation_change(self, e):
        """Обработчик смены страницы"""
        self.current_page_index = e.control.selected_index

        if self.current_page_index == 0:
            self.page_content.content = self.feed_page.build(page=self.page)
        elif self.current_page_index == 1:
            self.page_content.content = self.sources_page.build(page=self.page)
        elif self.current_page_index == 2:
            self.page_content.content = self.settings_page.build(page=self.page)

        self.page.update()

    def build_sources_page(self):
        """Создать страницу источников"""
        sources_list = self._build_sources_list()
        self.sources_column = sources_list

        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Источники новостей", size=26, weight=ft.FontWeight.BOLD),
                        ft.Text("Управление RSS-лентами и другими источниками", size=14, color=ft.Colors.GREY),
                    ]),
                    padding=20
                ),
                ft.Divider(),
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.ElevatedButton("Добавить RSS-ленту", icon=ft.Icons.ADD, on_click=self.add_rss_source),
                            ft.ElevatedButton("Запустить парсинг", icon=ft.Icons.PLAY_ARROW, on_click=self.run_parsing),
                        ]),
                        ft.Container(height=10),
                        ft.Text("Подключённые источники:", weight=ft.FontWeight.BOLD, size=16),
                        sources_list,
                    ], spacing=10),
                    padding=20,
                    expand=True
                )
            ]),
            expand=True
        )

    def _build_sources_list(self):
        """Построить список подключённых источников"""
        if not self.repository:
            return ft.Text("База данных не подключена", color=ft.Colors.RED)

        try:
            sources = self.repository.get_active_sources()
            if not sources:
                return ft.Text("Нет подключённых источников. Добавьте RSS-ленту.", color=ft.Colors.GREY)

            controls = []
            for source in sources:
                controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.RSS_FEED, color=ft.Colors.BLUE),
                        title=ft.Text(source.name),
                        subtitle=ft.Text(f"Тип: {source.type}"),
                        trailing=ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN) if source.is_active else ft.Icon(ft.Icons.PAUSE_CIRCLE, color=ft.Colors.GREY),
                    )
                )
            return ft.Column(controls, spacing=5)
        except Exception as e:
            return ft.Text(f"Ошибка загрузки источников: {e}", color=ft.Colors.RED)

    def build_settings_page(self):
        """Создать страницу настроек"""
        self.ollama_host_field = ft.TextField(label="Ollama Host", value="http://localhost:11434", width=300)
        self.ollama_model_field = ft.TextField(label="Model", value="mistral:7b", width=300)
        self.parse_interval_field = ft.TextField(label="Интервал парсинга (мин)", value="30", width=300)
        self.theme_switch = ft.Switch(label="Тёмная тема", value=True, on_change=self.toggle_theme)
        self.auto_update_switch = ft.Switch(label="Автообновление UI", value=self.auto_update_enabled, on_change=self.toggle_auto_update)

        db_stats = self._get_db_stats()

        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Настройки", size=26, weight=ft.FontWeight.BOLD),
                        ft.Text("Конфигурация приложения", size=14, color=ft.Colors.GREY),
                    ]),
                    padding=20
                ),
                ft.Divider(),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Ollama", weight=ft.FontWeight.BOLD, size=18),
                        self.ollama_host_field,
                        self.ollama_model_field,
                        ft.ElevatedButton("Проверить подключение", icon=ft.Icons.LINK, on_click=self.test_ollama),
                        ft.Container(height=20),
                        ft.Text("Парсинг", weight=ft.FontWeight.BOLD, size=18),
                        self.parse_interval_field,
                        ft.Container(height=20),
                        ft.Text("Интерфейс", weight=ft.FontWeight.BOLD, size=18),
                        self.theme_switch,
                        self.auto_update_switch,
                        ft.Container(height=20),
                        ft.Text("Статистика", weight=ft.FontWeight.BOLD, size=18),
                        ft.Text(db_stats, size=14, color=ft.Colors.GREY),
                        ft.Container(height=20),
                        ft.ElevatedButton("Сохранить настройки", icon=ft.Icons.SAVE, on_click=self.save_settings),
                    ], spacing=10),
                    padding=20,
                    width=400
                )
            ]),
            expand=True
        )

    def _get_db_stats(self):
        """Получить статистику из БД"""
        if not self.repository:
            return "База данных не подключена"
        try:
            all_articles = self.repository.get_articles(limit=999999)
            categories = self.repository.get_categories()
            sources = self.repository.get_sources()
            read_count = sum(1 for a in all_articles if a.is_read)
            return (
                f"Всего новостей: {len(all_articles)}\n"
                f"Категорий: {len(categories)} ({', '.join(categories)})\n"
                f"Источников: {len(sources)} ({', '.join(sources)})\n"
                f"Прочитано: {read_count}, Непрочитано: {len(all_articles) - read_count}"
            )
        except Exception as e:
            return f"Ошибка: {e}"

    def run_parsing(self, e):
        """Запустить парсинг источников"""
        if not self.orchestrator:
            self.page.show_dialog(ft.SnackBar(ft.Text("Парсер не инициализирован")))
            return

        self.page.show_dialog(ft.SnackBar(ft.Text("Запуск парсинга...")))

        def run_parsing_thread():
            try:
                count = self.orchestrator.run_full_cycle()

                async def update_ui():
                    status = "Парсинг завершён!" if count > 0 else "Новых новостей нет"
                    self.page.show_dialog(ft.SnackBar(ft.Text(f"{status} Обработано {count}")))
                    self.feed_page.refresh()
                    if self.current_page_index == 1:
                        self.page_content.content = self.build_sources_page()
                    self.page.update()
                self.page.run_task(update_ui)
            except Exception as ex:
                async def show_error():
                    self.page.show_dialog(ft.SnackBar(ft.Text(f"Ошибка парсинга: {str(ex)}")))
                self.page.run_task(show_error)

        threading.Thread(target=run_parsing_thread, daemon=True).start()

    def add_rss_source(self, e):
        """Добавить RSS источник"""
        url_field = ft.TextField(
            label="URL RSS ленты",
            hint_text="https://example.com/rss",
            width=400
        )

        name_field = ft.TextField(
            label="Название",
            hint_text="Например: РИА Новости",
            width=400
        )

        def close_dialog(e):
            self.page.pop_dialog()
            self.page.update()

        def save_source(e):
            url = url_field.value.strip()
            name = name_field.value.strip()

            if not url:
                self.page.show_dialog(ft.SnackBar(ft.Text("Введите URL источника")))
                return

            if not name:
                name = url

            try:
                import json
                from news_analyzer.db.models import Source
                from datetime import datetime

                source = Source(
                    type="rss",
                    name=name,
                    config=json.dumps({"url": url}),
                    is_active=True,
                    last_fetch=None
                )
                self.repository.save_source(source)

                self.page.show_dialog(ft.SnackBar(ft.Text(f"Источник добавлен: {name}")))
                self.page.pop_dialog()

                if self.current_page_index == 1:
                    self.page_content.content = self.build_sources_page()
                self.page.update()
            except Exception as ex:
                self.page.show_dialog(ft.SnackBar(ft.Text(f"Ошибка: {str(ex)}")))

        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Добавить RSS источник"),
            content=ft.Column([
                name_field,
                url_field,
                ft.Text("Поддерживаются RSS/Atom ленты новостных сайтов", size=12, color=ft.Colors.GREY),
            ], tight=True),
            actions=[
                ft.TextButton("Отмена", on_click=close_dialog),
                ft.ElevatedButton("Добавить", on_click=save_source),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    def test_ollama(self, e):
        """Проверить Ollama"""
        host = self.ollama_host_field.value.rstrip('/')
        model = self.ollama_model_field.value

        if self.orchestrator and self.orchestrator.ai_agent:
            self.orchestrator.ai_agent.host = host
            self.orchestrator.ai_agent.model_name = model
            self.orchestrator.ai_agent.api_url = f"{host}/api/generate"

            connected = self.orchestrator.ai_agent.validate_connection()

            if connected:
                self.page.show_dialog(ft.SnackBar(ft.Text(f"Ollama подключён! Модель: {model}")))
            else:
                self.page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось подключиться к Ollama. Убедитесь, что сервис запущен на {host}")))
            self.page.update()
        else:
            self.page.show_dialog(ft.SnackBar(ft.Text("ИИ-агент не инициализирован")))

    def toggle_theme(self, e):
        """Переключить тему"""
        self.page.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        self.page.update()

    def toggle_auto_update(self, e):
        """Переключить автообновление"""
        self.auto_update_enabled = e.control.value
        status = "включено" if self.auto_update_enabled else "отключено"
        self.page.show_dialog(ft.SnackBar(ft.Text(f"Автообновление {status}")))

    def save_settings(self, e):
        """Сохранить настройки"""
        self.page.show_dialog(ft.SnackBar(ft.Text("Настройки сохранены")))

    def on_close(self, e=None):
        """Обработчик закрытия приложения"""
        print("Приложение закрывается...")
        return True


def main(page: ft.Page):
    """Главная функция приложения"""
    app = NewsAnalyzerApp()
    app.main(page)


if __name__ == "__main__":
    ft.run(main)
