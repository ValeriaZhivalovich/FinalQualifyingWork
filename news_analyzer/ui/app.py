import flet as ft


def main(page: ft.Page):
    """Главная функция Flet приложения"""
    page.title = "News Analyzer"
    page.theme_mode = ft.ThemeMode.LIGHT

    # TODO: Implement UI pages and navigation
    page.add(ft.Text("News Analyzer", size=30, weight=ft.FontWeight.BOLD))
    page.add(ft.Text("Приложение для анализа новостных лент"))
    page.add(ft.ElevatedButton("Загрузить новости", on_click=lambda e: print("Fetch news")))


if __name__ == "__main__":
    ft.app(target=main)