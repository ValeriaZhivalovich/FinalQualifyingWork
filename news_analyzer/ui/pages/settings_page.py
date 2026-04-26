import flet as ft


class SettingsPage:
    """Страница настроек"""

    def build(self) -> ft.Container:
        """Построить страницу"""
        return ft.Container(
            content=ft.Column([
                ft.Text("Настройки", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                ft.Text("Ollama:", weight=ft.FontWeight.BOLD),
                ft.TextField(label="Host", value="http://localhost:11434"),
                ft.TextField(label="Model", value="mistral:7b"),
                ft.ElevatedButton("Проверить подключение", on_click=self.test_ollama),
                ft.Container(height=20),
                ft.Text("Парсинг:", weight=ft.FontWeight.BOLD),
                ft.TextField(label="Интервал (минуты)", value="30"),
                ft.Container(height=20),
                ft.ElevatedButton("Сохранить настройки", on_click=self.save_settings),
            ], spacing=10),
            padding=20
        )

    def test_ollama(self, e):
        """Проверить подключение к Ollama"""
        # TODO: Проверить подключение
        print("Test Ollama connection")

    def save_settings(self, e):
        """Сохранить настройки"""
        # TODO: Сохранить в конфиг
        print("Save settings")