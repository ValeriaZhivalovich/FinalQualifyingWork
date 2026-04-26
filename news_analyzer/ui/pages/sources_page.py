import flet as ft


class SourcesPage:
    """Страница управления источниками"""

    def build(self) -> ft.Container:
        """Построить страницу"""
        return ft.Container(
            content=ft.Column([
                ft.Text("Источники", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("Управление источниками новостей", size=16),
                ft.Container(height=20),
                ft.ElevatedButton("Добавить RSS-ленту", on_click=self.add_rss_feed),
                ft.ElevatedButton("Запустить парсинг", on_click=self.run_parsing),
                ft.Container(height=20),
                ft.Text("Текущие источники:", weight=ft.FontWeight.BOLD),
                # TODO: Список источников из БД
                ft.Text("• RSS: РИА Новости"),
                ft.Text("• RSS: Lenta.ru"),
            ], spacing=10),
            padding=20
        )

    def add_rss_feed(self, e):
        """Добавить новую RSS-ленту"""
        # TODO: Диалог для добавления
        print("Add RSS feed")

    def run_parsing(self, e):
        """Запустить парсинг"""
        # TODO: Запустить pipeline
        print("Run parsing")