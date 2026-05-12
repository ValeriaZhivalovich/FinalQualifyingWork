import flet as ft
import json


class SourcesPage:
    def __init__(self, repository=None, orchestrator=None):
        self.repository = repository
        self.orchestrator = orchestrator
        self.page = None
        self.sources_list_container = ft.Column(controls=[], spacing=5)
        self.container = None

    def build(self, page=None) -> ft.Container:
        """Build the sources page UI"""
        self.page = page
        self._populate_sources_list()

        header = ft.Container(
            content=ft.Column([
                ft.Text("Источники новостей", size=26, weight=ft.FontWeight.BOLD),
                ft.Text("Управление RSS-лентами и другими источниками", size=14, color=ft.Colors.GREY),
            ]),
            padding=20
        )

        actions = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.ElevatedButton("Добавить RSS-ленту", icon=ft.Icons.ADD, on_click=self._show_add_rss_dialog),
                    ft.ElevatedButton("Запустить парсинг", icon=ft.Icons.PLAY_ARROW, on_click=self._run_parsing),
                ]),
                ft.Container(height=10),
                ft.Text("Подключённые источники:", weight=ft.FontWeight.BOLD, size=16),
                self.sources_list_container,
            ], spacing=10),
            padding=20
        )

        self.container = ft.Container(content=ft.Column([header, ft.Divider(), actions]), expand=True)
        return self.container

    def _populate_sources_list(self):
        self.sources_list_container.controls.clear()

        # 1. Активные коллекторы (из orchestrator)
        if self.orchestrator and hasattr(self.orchestrator, 'collectors'):
            source_icons = {
                "rss": ft.Icons.RSS_FEED,
                "vk": ft.Icons.GROUP,
                "vk_wave": ft.Icons.GROUP,
                "telegram": ft.Icons.SEND,
                "telegram_telethon": ft.Icons.SEND,
                "telegram_pyrogram": ft.Icons.SEND,
                "twitter_twikit": ft.Icons.ALTERNATE_EMAIL,
                "reddit": ft.Icons.FORUM,
                "reddit_async": ft.Icons.FORUM,
            }
            active = [c for c in self.orchestrator.collectors if c.validate_config()]
            if active:
                self.sources_list_container.controls.append(
                    ft.Text("Системные источники:", weight=ft.FontWeight.BOLD, size=14)
                )
                for c in active:
                    name = getattr(c, 'source_name', 'unknown')
                    icon = source_icons.get(name, ft.Icons.LINK)
                    self.sources_list_container.controls.append(
                        ft.ListTile(
                            leading=ft.Icon(icon, color=ft.Colors.GREEN),
                            title=ft.Text(name),
                            subtitle=ft.Text("Активен"),
                            trailing=ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN),
                        )
                    )

        # 2. Пользовательские источники из БД (RSS, добавленные вручную)
        if self.repository:
            try:
                sources = self.repository.get_active_sources()
                if sources:
                    self.sources_list_container.controls.append(
                        ft.Text("Пользовательские источники:", weight=ft.FontWeight.BOLD, size=14)
                    )
                    for source in sources:
                        self.sources_list_container.controls.append(
                            ft.ListTile(
                                leading=ft.Icon(ft.Icons.RSS_FEED, color=ft.Colors.BLUE),
                                title=ft.Text(source.name),
                                subtitle=ft.Text(f"Тип: {source.type}"),
                                trailing=ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN) if source.is_active else ft.Icon(ft.Icons.PAUSE_CIRCLE, color=ft.Colors.GREY),
                            )
                        )
            except Exception as e:
                self.sources_list_container.controls.append(ft.Text(f"Ошибка загрузки источников: {e}", color=ft.Colors.RED))

        if not self.sources_list_container.controls:
            self.sources_list_container.controls.append(ft.Text("Нет подключённых источников", color=ft.Colors.GREY))

    def _show_add_rss_dialog(self, e):
        """Show dialog to add RSS source"""
        if not self.page:
            return

        name_field = ft.TextField(label="Название", width=400)
        url_field = ft.TextField(label="URL RSS ленты", hint_text="https://...", width=400)

        def close_dialog(e):
            self.page.pop_dialog()
            self.page.update()

        def save_source(e):
            url = url_field.value.strip()
            name = name_field.value.strip() or url

            if not url:
                self.page.show_dialog(ft.SnackBar(ft.Text("Введите URL")))
                return

            try:
                from news_analyzer.db.models import Source
                source = Source(
                    type="rss",
                    name=name,
                    config=json.dumps({"url": url}),
                    is_active=True,
                )
                self.repository.save_source(source)
                self.page.show_dialog(ft.SnackBar(ft.Text(f"Добавлен: {name}")))
                self.page.pop_dialog()
                self._populate_sources_list()
                self.page.update()
            except Exception as ex:
                self.page.show_dialog(ft.SnackBar(ft.Text(f"Ошибка: {ex}")))

        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Добавить RSS-ленту"),
            content=ft.Column([name_field, url_field], tight=True),
            actions=[
                ft.TextButton("Отмена", on_click=close_dialog),
                ft.ElevatedButton("Добавить", on_click=save_source),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    def _run_parsing(self, e):
        """Run parsing cycle"""
        if not self.page:
            return

        if not self.orchestrator:
            self.page.show_dialog(ft.SnackBar(ft.Text("Парсер не инициализирован")))
            return

        import threading

        def parse():
            try:
                count = self.orchestrator.run_full_cycle()

                async def update_ui():
                    self.page.show_dialog(ft.SnackBar(ft.Text(f"Обработано {count} новостей")))
                    self._populate_sources_list()
                    self.page.update()
                self.page.run_task(update_ui)
            except Exception as ex:
                async def show_error():
                    self.page.show_dialog(ft.SnackBar(ft.Text(f"Ошибка: {ex}")))
                self.page.run_task(show_error)

        threading.Thread(target=parse, daemon=True).start()
