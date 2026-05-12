import flet as ft


class FeedPage:
    """Страница ленты новостей"""

    def __init__(self, repository=None, orchestrator=None):
        self.repository = repository
        self.orchestrator = orchestrator
        self.refresh_callback = None
        self.all_articles = []
        self.articles = []
        self.show_unread_only = False
        self.page = None

        # UI elements
        self.category_filter = None
        self.source_filter = None
        self.search_field = None
        self.unread_switch = None
        self.articles_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
            expand=True
        )
        self.container = None

    def build(self, page=None) -> ft.Container:
        """Build the feed page UI"""
        self.page = page
        self.load_articles()

        header = self._build_header()

        self.container = ft.Container(
            content=ft.Column([
                header,
                ft.Divider(),
                self.articles_column
            ]),
            expand=True
        )

        return self.container

    def set_refresh_callback(self, cb):
        self.refresh_callback = cb

    def _notify_parent(self):
        if callable(self.refresh_callback):
            self.refresh_callback()

    def refresh(self):
        self.load_articles()
        self._apply_filters()
        self.articles_column.controls = self._build_article_cards()
        if self.page:
            self.page.update()

    def _apply_filters_and_refresh(self, e=None):
        self.refresh()
        self._notify_parent()

    def _build_header(self):
        self.category_filter = ft.Dropdown(
            label="Категория",
            options=[ft.DropdownOption(key=c, text=c) for c in ["Все", "политика", "технологии", "экономика", "спорт", "культура", "прочее"]],
            value="Все",
            width=180,
            on_select=lambda e: self._apply_filters_and_refresh(),
        )
        self.source_filter = ft.Dropdown(
            label="Источник",
            options=[ft.DropdownOption(key=s, text=s) for s in ["Все", "rss", "telegram", "vk"]],
            value="Все",
            width=180,
            on_select=lambda e: self._apply_filters_and_refresh(),
        )
        self.search_field = ft.TextField(
            label="Поиск",
            hint_text="Поиск по заголовку...",
            width=250,
            on_submit=lambda e: self._apply_filters_and_refresh(),
        )
        self.unread_switch = ft.Switch(
            label="Только непрочитанные",
            value=False,
            on_change=lambda e: self._apply_filters_and_refresh(),
        )

        def on_refresh(e):
            self._apply_filters_and_refresh()

        return ft.Container(
            content=ft.Column([
                ft.Text("Лента новостей", size=26, weight=ft.FontWeight.BOLD),
                ft.Row([
                    self.category_filter,
                    self.source_filter,
                    self.search_field,
                    self.unread_switch,
                    ft.ElevatedButton("Обновить", icon=ft.Icons.REFRESH, on_click=on_refresh),
                ], spacing=10, wrap=True),
            ]),
            padding=20,
        )

    def load_articles(self):
        """Загрузить статьи из БД"""
        if not self.repository:
            self.all_articles = []
            return
        try:
            db_articles = self.repository.get_articles(limit=100)
            self.all_articles = [
                {
                    'id': a.id,
                    'source': a.source,
                    'title': a.title or "Без заголовка",
                    'summary': a.summary or "Без описания",
                    'category': a.category or "прочее",
                    'published_at': a.published_at.strftime("%Y-%m-%d %H:%M") if a.published_at else "Неизвестно",
                    'url': a.url or "#",
                    'is_read': bool(a.is_read),
                }
                for a in db_articles
            ]
        except Exception as e:
            print(f"Error loading articles: {e}")
            self.all_articles = []

    def _apply_filters(self):
        """Применить фильтры"""
        if not self.category_filter or not self.source_filter or not self.search_field or not self.unread_switch:
            self.articles = self.all_articles
            return

        self.show_unread_only = self.unread_switch.value

        filtered = self.all_articles
        if self.show_unread_only:
            filtered = [a for a in filtered if not a['is_read']]

        category = self.category_filter.value
        if category and category != "Все":
            filtered = [a for a in filtered if a['category'] == category]

        source = self.source_filter.value
        if source and source != "Все":
            filtered = [a for a in filtered if a['source'] == source]

        search = self.search_field.value.strip().lower() if self.search_field.value else ""
        if search:
            filtered = [a for a in filtered if search in a['title'].lower() or search in a['summary'].lower()]

        self.articles = filtered

    def _build_article_cards(self) -> list:
        """Build article card widgets"""
        if not self.articles:
            return [
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.RSS_FEED, size=48, color=ft.Colors.GREY),
                        ft.Text("Новостей нет", size=20),
                        ft.Text("Запустите парсинг для загрузки новостей", color=ft.Colors.GREY),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                )
            ]

        category_colors = {
            "технологии": ft.Colors.BLUE,
            "политика": ft.Colors.RED,
            "экономика": ft.Colors.GREEN,
            "спорт": ft.Colors.ORANGE,
            "культура": ft.Colors.PURPLE,
            "прочее": ft.Colors.GREY,
        }
        source_icons = {
            "rss": ft.Icons.RSS_FEED,
            "telegram": ft.Icons.SEND,
            "vk": ft.Icons.GROUP,
        }

        cards = []
        for a in self.articles:
            def mark_read(e, aid=a['id']):
                if self.repository:
                    self.repository.mark_as_read(aid)
                    self._apply_filters_and_refresh()

            def open_url(e, url=a.get('url')):
                if url and url != '#' and self.page:
                    async def _launch():
                        await self.page.launch_url(url)
                    self.page.run_task(_launch)

            cards.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(source_icons.get(a['source'], ft.Icons.LINK), size=14),
                                ft.Text(a['source'].capitalize(), size=12, color=ft.Colors.GREY),
                                ft.Chip(label=ft.Text(a['category'], size=10), bgcolor=category_colors.get(a['category'], ft.Colors.GREY_700)),
                                ft.Text(a['published_at'], size=12, color=ft.Colors.GREY),
                                ft.Icon(ft.Icons.CHECK_CIRCLE if a['is_read'] else ft.Icons.RADIO_BUTTON_UNCHECKED, size=16, color=ft.Colors.GREEN if a['is_read'] else ft.Colors.GREY),
                            ], wrap=True),
                            ft.Text(a['title'], size=16, weight=ft.FontWeight.BOLD),
                            ft.Text(a['summary'], size=14),
                            ft.Row([
                                ft.TextButton("Открыть", on_click=open_url),
                                ft.TextButton("Прочитано", on_click=mark_read, disabled=a['is_read']),
                            ]),
                        ]),
                        padding=15,
                    )
                )
            )
        return cards
