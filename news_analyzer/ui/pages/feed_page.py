import flet as ft
from typing import List


class FeedPage:
    """Страница ленты новостей"""

    def __init__(self):
        self.articles = []  # TODO: Получать из базы данных
        self.category_filter = ft.Dropdown(
            label="Категория",
            options=[
                ft.dropdown.Option("Все"),
                ft.dropdown.Option("политика"),
                ft.dropdown.Option("технологии"),
                ft.dropdown.Option("экономика"),
                ft.dropdown.Option("спорт"),
                ft.dropdown.Option("культура"),
                ft.dropdown.Option("прочее"),
            ],
            value="Все",
            width=200,
        )

        self.source_filter = ft.Dropdown(
            label="Источник",
            options=[
                ft.dropdown.Option("Все"),
                ft.dropdown.Option("rss"),
                ft.dropdown.Option("telegram"),
                ft.dropdown.Option("vk"),
            ],
            value="Все",
            width=200,
        )

        self.search_field = ft.TextField(
            label="Поиск",
            width=300,
            on_change=self.on_search_change
        )

        self.articles_list = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=10)

    def build(self) -> ft.Container:
        """Построить страницу"""
        # Заголовок и фильтры
        header = ft.Container(
            content=ft.Column([
                ft.Text("Лента новостей", size=24, weight=ft.FontWeight.BOLD),
                ft.Row([
                    self.category_filter,
                    self.source_filter,
                    self.search_field,
                    ft.ElevatedButton("Обновить", on_click=self.on_refresh_click),
                ], spacing=10),
            ]),
            padding=20
        )

        # Список новостей
        self.load_articles()

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(),
                self.articles_list
            ]),
            expand=True
        )

    def load_articles(self):
        """Загрузить статьи из базы данных"""
        # TODO: Реализовать загрузку из БД
        # Пока показываем тестовые данные
        self.articles_list.controls.clear()

        if not self.articles:
            self.articles = self._get_mock_articles()

        for article in self.articles:
            article_card = self._create_article_card(article)
            self.articles_list.controls.append(article_card)

        self.articles_list.update()

    def _create_article_card(self, article) -> ft.Card:
        """Создать карточку статьи"""
        # Handle Flet version differences for colors
        if hasattr(ft, 'colors'):
            colors_module = ft.colors
        else:
            colors_module = ft.Colors

        category_colors = {
            "политика": colors_module.BLUE,
            "технологии": colors_module.GREEN,
            "экономика": colors_module.ORANGE,
            "спорт": colors_module.RED,
            "культура": colors_module.PURPLE,
            "прочее": colors_module.GREY,
        }

        category_color = category_colors.get(article.get('category', 'прочее'), colors_module.GREY)

        # Handle source text color for Flet version differences
        source_color = colors_module.GREY

        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(article['source'], size=12, color=ft.Colors.GREY),
                        ft.Container(width=10),
                        ft.Chip(
                            label=ft.Text(article['category'], size=10),
                            bgcolor=category_color,
                            color=ft.Colors.WHITE,
                        ),
                        ft.Container(width=10),
                        ft.Text(article['published_at'], size=12, color=ft.Colors.GREY),
                    ]),
                    ft.Text(article['title'], size=16, weight=ft.FontWeight.BOLD),
                    ft.Text(article['summary'], size=14),
                    ft.Row([
                        ft.TextButton("Открыть", url=article.get('url')),
                        ft.TextButton("Прочитано", on_click=lambda e: self.mark_as_read(article['id'])),
                    ])
                ]),
                padding=15
            )
        )

    def _get_mock_articles(self) -> List[dict]:
        """Тестовые данные для демонстрации"""
        return [
            {
                'id': 1,
                'source': 'rss',
                'title': 'Тестовая новость 1',
                'summary': 'Это краткое резюме первой тестовой новости для демонстрации интерфейса.',
                'category': 'технологии',
                'published_at': '2024-01-15 10:30',
                'url': 'https://example.com/news1'
            },
            {
                'id': 2,
                'source': 'rss',
                'title': 'Тестовая новость 2',
                'summary': 'Вторая тестовая новость о политике для проверки фильтров.',
                'category': 'политика',
                'published_at': '2024-01-15 09:15',
                'url': 'https://example.com/news2'
            }
        ]

    def on_search_change(self, e):
        """Обработчик изменения поиска"""
        # TODO: Реализовать поиск
        pass

    def on_refresh_click(self, e):
        """Обработчик кнопки обновления"""
        # TODO: Запустить парсинг
        print("Refresh clicked")

    def mark_as_read(self, article_id):
        """Отметить статью как прочитанную"""
        # TODO: Обновить в БД
        print(f"Mark as read: {article_id}")