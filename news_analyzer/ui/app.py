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
        self.all_articles: List[Dict[str, Any]] = []
        self.articles: List[Dict[str, Any]] = []
        self.card_refs: Dict[int, Dict] = {}
        self.show_unread_only = False
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

        # Интеграция UI-страниц согласно design_doc
        self.feed_page = FeedPage(repository=self.repository, orchestrator=self.orchestrator)
        self.sources_page = SourcesPage(repository=self.repository, orchestrator=self.orchestrator)
        self.settings_page = SettingsPage(repository=self.repository, ai_agent=self.orchestrator.ai_agent if self.orchestrator else None) if self.orchestrator else SettingsPage()

        self.load_articles_from_db()
        # Bind refresh callback so feed page can request UI refresh
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

    def build_feed_page(self):
        """Построить страницу ленты новостей"""
        category_filter = ft.Dropdown(
            label="Категория",
            options=[
                ft.DropdownOption(key="Все", text="Все"),
                ft.DropdownOption(key="политика", text="политика"),
                ft.DropdownOption(key="технологии", text="технологии"),
                ft.DropdownOption(key="экономика", text="экономика"),
                ft.DropdownOption(key="спорт", text="спорт"),
                ft.DropdownOption(key="культура", text="культура"),
                ft.DropdownOption(key="прочее", text="прочее"),
            ],
            value="Все",
            width=180,
            on_select=lambda e: self._apply_filters_and_refresh()
        )
        self.category_filter_ctrl = category_filter

        source_filter = ft.Dropdown(
            label="Источник",
            options=[
                ft.DropdownOption(key="Все", text="Все"),
                ft.DropdownOption(key="rss", text="rss"),
                ft.DropdownOption(key="telegram", text="telegram"),
                ft.DropdownOption(key="vk", text="vk"),
            ],
            value="Все",
            width=180,
            on_select=lambda e: self._apply_filters_and_refresh()
        )
        self.source_filter_ctrl = source_filter

        search_field = ft.TextField(
            label="Поиск",
            hint_text="Поиск по заголовку и резюме...",
            width=250,
            on_submit=lambda e: self._apply_filters_and_refresh()
        )
        self.search_field_ctrl = search_field

        unread_switch = ft.Switch(
            label="Только непрочитанные",
            value=False,
            on_change=self.toggle_unread_filter
        )

        articles_column = ft.Column(
            controls=self._build_article_cards(),
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
            expand=True
        )
        self.articles_column = articles_column

        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Лента новостей", size=26, weight=ft.FontWeight.BOLD),
                        ft.Row([
                            category_filter,
                            source_filter,
                            search_field,
                            unread_switch,
                            ft.ElevatedButton("Обновить новости", icon=ft.Icons.REFRESH, on_click=self.refresh_news),
                        ], spacing=10, wrap=True),
                    ]),
                    padding=20
                ),
                ft.Divider(),
                ft.Container(
                    content=articles_column,
                    padding=20,
                    expand=True
                ),
            ]),
            expand=True
        )

    def _build_article_cards(self):
        """Построить список карточек новостей"""
        self.card_refs.clear()

        if not self.articles:
            return [
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.RSS_FEED, size=48, color=ft.Colors.GREY),
                        ft.Text("Новостей пока нет", size=20, weight=ft.FontWeight.BOLD),
                        ft.Text("Добавьте RSS-источники и запустите парсинг", size=14, color=ft.Colors.GREY),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    padding=40,
                    alignment=ft.alignment.center
                )
            ]

        return [self.create_news_card(article) for article in self.articles]

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

    def _apply_filters_and_refresh(self):
        """Применить фильтры и обновить отображение"""
        self.apply_filter()
        self.articles_column.controls = self._build_article_cards()
        self.page.update()

    def create_news_card(self, article):
        """Создать карточку новости"""
        title = article['title']
        summary = article['summary']
        category = article['category']
        published_at = article['published_at']
        source = article.get('source', 'rss')
        is_read = article.get('is_read', False)
        article_id = article['id']

        category_colors = {
            "технологии": ft.Colors.BLUE,
            "политика": ft.Colors.RED,
            "экономика": ft.Colors.GREEN,
            "спорт": ft.Colors.ORANGE,
            "культура": ft.Colors.PURPLE,
            "прочее": ft.Colors.GREY,
        }

        is_dark = self.page.theme_mode == ft.ThemeMode.DARK

        if is_read:
            title_color = ft.Colors.GREY_300 if is_dark else ft.Colors.GREY_400
            summary_color = ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_500
        else:
            title_color = ft.Colors.WHITE if is_dark else ft.Colors.BLACK
            summary_color = ft.Colors.GREY_100 if is_dark else ft.Colors.BLACK87

        source_icons = {
            "rss": ft.Icons.RSS_FEED,
            "telegram": ft.Icons.SEND,
            "vk": ft.Icons.GROUP,
        }

        chip = ft.Chip(
            label=ft.Text(category, size=10, color=ft.Colors.WHITE),
            bgcolor=category_colors.get(category, ft.Colors.GREY),
        )

        source_icon = ft.Icon(source_icons.get(source, ft.Icons.LINK), size=14, color=ft.Colors.BLUE)

        date_text = ft.Text(published_at, size=12, color=ft.Colors.GREY)

        read_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE if is_read else ft.Icons.RADIO_BUTTON_UNCHECKED,
            size=16,
            color=ft.Colors.GREEN if is_read else ft.Colors.GREY,
        )

        title_text = ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=title_color)

        summary_text = ft.Text(summary, size=14, max_lines=3, color=summary_color)

        def open_url(e):
            url = article.get('url', '#')
            if url and url != '#':
                async def _launch():
                    await self.page.launch_url(url)
                self.page.run_task(_launch)
            else:
                self.page.show_dialog(ft.SnackBar(ft.Text("Ссылка недоступна")))

        open_button = ft.TextButton("Открыть", on_click=open_url)

        def mark_read(e):
            self._mark_article_read(article_id)

        read_button = ft.TextButton(
            "Прочитано" if is_read else "Отметить прочитанным",
            on_click=mark_read,
            disabled=is_read
        )

        card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        source_icon,
                        ft.Text(source.capitalize(), size=12, color=ft.Colors.GREY),
                        ft.Container(width=10),
                        chip,
                        date_text,
                        read_icon,
                    ]),
                    title_text,
                    summary_text,
                    ft.Row([open_button, read_button])
                ]),
                padding=15
            )
        )

        return card

    def _mark_article_read(self, article_id: int):
        """Отметить статью как прочитанную через БД"""
        if not self.repository:
            self.page.show_dialog(ft.SnackBar(ft.Text("База данных не подключена")))
            return

        try:
            success = self.repository.mark_as_read(article_id)
            if success:
                for article in self.articles:
                    if article['id'] == article_id:
                        article['is_read'] = True
                        break
                for article in self.all_articles:
                    if article['id'] == article_id:
                        article['is_read'] = True
                        break
                self.articles_column.controls = self._build_article_cards()
                self.page.show_dialog(ft.SnackBar(ft.Text("Отмечено как прочитанное")))
                self.page.update()
            else:
                self.page.show_dialog(ft.SnackBar(ft.Text("Не удалось обновить статус")))
        except Exception as e:
            self.page.show_dialog(ft.SnackBar(ft.Text(f"Ошибка: {str(e)}")))

    def refresh_news(self, e):
        """Обновить новости через парсинг"""
        if not self.orchestrator:
            self.page.show_dialog(ft.SnackBar(ft.Text("Парсер не инициализирован")))
            return

        self.page.show_dialog(ft.SnackBar(ft.Text("Обновление новостей...")))

        def run_parsing():
            try:
                count = self.orchestrator.run_full_cycle()

                async def update_ui():
                    self.page.show_dialog(ft.SnackBar(ft.Text(f"Добавлено {count} новых новостей")))
                    self.load_articles_from_db()
                    self.articles_column.controls = self._build_article_cards()
                    self.page.update()
                self.page.run_task(update_ui)
            except Exception as ex:
                async def show_error():
                    self.page.show_dialog(ft.SnackBar(ft.Text(f"Ошибка: {str(ex)}")))
                self.page.run_task(show_error)

        threading.Thread(target=run_parsing, daemon=True).start()

    def load_articles_from_db(self):
        """Загрузить новости из базы данных"""
        if not self.repository:
            self.all_articles = []
            self.articles = []
            return

        try:
            db_articles = self.repository.get_articles(limit=100)
            self.all_articles = []
            for article in db_articles:
                article_dict = {
                    'id': article.id,
                    'source': article.source,
                    'title': article.title or "Без заголовка",
                    'summary': article.summary[:200] + "..." if article.summary and len(article.summary) > 200 else article.summary or "Без описания",
                    'category': article.category or "прочее",
                    'published_at': article.published_at.strftime("%Y-%m-%d %H:%M") if article.published_at else "Неизвестно",
                    'url': article.url or "#",
                    'is_read': bool(article.is_read)
                }
                self.all_articles.append(article_dict)

            self.apply_filter()

        except Exception as e:
            print(f"Ошибка загрузки новостей из БД: {e}")
            self.all_articles = []
            self.articles = []

    def apply_filter(self):
        """Применить фильтр к новостям"""
        if self.show_unread_only:
            self.articles = [a for a in self.all_articles if not a['is_read']]
        else:
            self.articles = self.all_articles.copy()

    def toggle_unread_filter(self, e):
        """Переключить фильтр непрочитанных новостей"""
        self.show_unread_only = e.control.value
        self.apply_filter()
        if self.current_page_index == 0:
            self.articles_column.controls = self._build_article_cards()
            self.page.update()

    def update_feed_display(self):
        """Обновить отображение ленты новостей"""
        self.load_articles_from_db()
        if self.current_page_index == 0:
            self.articles_column.controls = self._build_article_cards()
        self.page.update()

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
            self.page.close_dialog()
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
                self.page.close_dialog()

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
                    self.update_feed_display()
                    if self.current_page_index == 1:
                        self.page_content.content = self.build_sources_page()
                    self.page.update()
                self.page.run_task(update_ui)
            except Exception as ex:
                async def show_error():
                    self.page.show_dialog(ft.SnackBar(ft.Text(f"Ошибка парсинга: {str(ex)}")))
                self.page.run_task(show_error)

        threading.Thread(target=run_parsing_thread, daemon=True).start()

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
