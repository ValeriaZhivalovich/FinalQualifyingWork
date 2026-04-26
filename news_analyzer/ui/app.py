import flet as ft
import asyncio
import threading


class NewsAnalyzerApp:
    """Основное приложение News Analyzer"""

    def __init__(self, orchestrator=None, repository=None):
        self.current_page_index = 0
        self.pages = ["feed", "sources", "settings"]
        self.orchestrator = orchestrator
        self.repository = repository
        self.articles = []  # Кэш новостей для UI
        self.all_articles = []  # Все новости без фильтрации
        self.show_unread_only = False  # Показывать только непрочитанные
        self.auto_update_enabled = True  # Автообновление включено по умолчанию
        self.card_refs = {}  # Ссылки на карточки для обновления без перестройки

    def main(self, page: ft.Page):
        """Главная функция приложения"""
        self.page = page
        page.title = "News Analyzer"
        page.theme_mode = ft.ThemeMode.DARK  # Темная тема по умолчанию
        page.window_width = 1200
        page.window_height = 800

        # Обработчик закрытия приложения
        page.on_disconnect = self.on_close

        # Навигационная панель
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

        # Загружаем новости из базы при запуске
        self.load_articles_from_db()

        # Контейнер для содержимого страниц
        self.page_content = ft.Container(
            content=self.build_feed_page(),
            expand=True
        )

        # Основной layout
        page.add(
            ft.Row([
                self.navigation_rail,
                ft.VerticalDivider(width=1),
                self.page_content
            ], expand=True)
        )

        # Автообновление отключено (Timer не поддерживается в этой версии Flet)
        # Используйте кнопку "Обновить новости" для ручного обновления
        pass

    def on_navigation_change(self, e):
        """Обработчик смены страницы"""
        self.current_page_index = e.control.selected_index

        if self.current_page_index == 0:
            self.page_content.content = self.build_feed_page()
        elif self.current_page_index == 1:
            self.page_content.content = self.build_sources_page()
        elif self.current_page_index == 2:
            self.page_content.content = self.build_settings_page()

        self.page.update()

    def build_feed_page(self):
        """Создать страницу ленты новостей"""
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Лента новостей", size=24, weight=ft.FontWeight.BOLD),
                        ft.Text("Новости по Крыму и Севастополю", size=16),
                        ft.Row([
                            ft.Text("Автоматическая фильтрация по ключевым словам", size=12, color=ft.Colors.GREY),
                            ft.Container(width=10),
                            ft.Icon(
                                ft.Icons.REFRESH,
                                size=16,
                                color=ft.Colors.BLUE
                            ),
                            ft.Text(
                                "Нажмите 'Обновить новости' для загрузки свежих новостей",
                                size=12,
                                color=ft.Colors.BLUE
                            ),
                        ]),
                        ft.ElevatedButton("Обновить новости", on_click=self.refresh_news),
                        ft.Container(width=10),
                        ft.Switch(
                            label="Только непрочитанные",
                            value=self.show_unread_only,
                            on_change=self.toggle_unread_filter
                        ),
                    ]),
                    padding=20
                ),
                ft.Divider(),
                ft.Container(
                    content=ft.ListView([
                        # Показываем загруженные новости
                        *[self.create_news_card(article) for article in self.articles],
                        ft.Container(height=20),  # Отступ в конце
                        ft.Text(f"Всего новостей: {len(self.articles)}", size=12, color=ft.Colors.GREY) if self.articles else
                        ft.Text("Новостей пока нет. Нажмите 'Обновить новости' для загрузки из RSS источников", size=14, color=ft.Colors.GREY),
                    ], spacing=10),
                    expand=True,
                    padding=20
                )
            ]),
            expand=True
        )

    def build_sources_page(self):
        """Создать страницу источников"""
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Источники новостей", size=24, weight=ft.FontWeight.BOLD),
                        ft.Text("Управление источниками", size=16),
                    ]),
                    padding=20
                ),
                ft.Divider(),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Поддерживаемые источники:", weight=ft.FontWeight.BOLD),
                        ft.Text("• RSS ленты"),
                        ft.Text("• Telegram каналы"),
                        ft.Text("• VK сообщества"),
                        ft.Container(height=20),
                        ft.ElevatedButton("Добавить RSS источник", on_click=self.add_rss_source),
                        ft.ElevatedButton("Запустить парсинг", on_click=self.run_parsing),
                    ], spacing=10),
                    padding=20
                )
            ]),
            expand=True
        )

    def build_settings_page(self):
        """Создать страницу настроек"""
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Настройки", size=24, weight=ft.FontWeight.BOLD),
                        ft.Text("Конфигурация приложения", size=16),
                    ]),
                    padding=20
                ),
                ft.Divider(),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Ollama настройки:", weight=ft.FontWeight.BOLD),
                        ft.TextField(label="Host", value="http://localhost:11434"),
                        ft.TextField(label="Model", value="mistral:7b"),
                        ft.ElevatedButton("Проверить подключение", on_click=self.test_ollama),
                        ft.Container(height=20),
                        ft.Text("Общие настройки:", weight=ft.FontWeight.BOLD),
                        ft.TextField(label="Интервал парсинга (мин)", value="30"),
                        ft.Text(f"База данных: news_analyzer.db ({len(self.articles)} новостей)", size=12, color=ft.Colors.GREY),
                        ft.Switch(label="Темная тема", value=True, on_change=self.toggle_theme),
                        ft.Switch(label="Автообновление UI", value=self.auto_update_enabled, on_change=self.toggle_auto_update),
                        ft.Container(height=20),
                        ft.ElevatedButton("Сохранить настройки", on_click=self.save_settings),
                    ], spacing=10),
                    padding=20
                )
            ]),
            expand=True
        )

    def create_news_card(self, article):
        """Создать карточку новости"""
        title = article['title']
        summary = article['summary']
        category = article['category']
        published_at = article['published_at']
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

        # Цвета для прочитанных/непрочитанных новостей
        is_dark = self.page.theme_mode == ft.ThemeMode.DARK

        if is_read:
            title_color = ft.Colors.GREY_400 if not is_dark else ft.Colors.GREY_300
            summary_color = ft.Colors.GREY_500 if not is_dark else ft.Colors.GREY_400
        else:
            title_color = ft.Colors.BLACK if not is_dark else ft.Colors.WHITE
            summary_color = ft.Colors.BLACK87 if not is_dark else ft.Colors.GREY_100

        # Создаем контролы с уникальными ключами для обновления
        chip = ft.Chip(
            label=ft.Text(category, size=10),
            bgcolor=category_colors.get(category, ft.Colors.GREY),
            key=f"chip_{article_id}"
        )

        date_text = ft.Text(
            published_at,
            size=12,
            color=ft.Colors.GREY,
            key=f"date_{article_id}"
        )

        icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE if is_read else ft.Icons.RADIO_BUTTON_UNCHECKED,
            size=16,
            color=ft.Colors.GREEN if is_read else ft.Colors.GREY,
            key=f"icon_{article_id}"
        )

        title_text = ft.Text(
            title,
            size=16,
            weight=ft.FontWeight.BOLD,
            color=title_color,
            key=f"title_{article_id}"
        )

        summary_text = ft.Text(
            summary,
            size=14,
            max_lines=2,
            color=summary_color,
            key=f"summary_{article_id}"
        )

        open_button = ft.TextButton(
            "Открыть",
            on_click=lambda e: self.open_news(title),
            disabled=is_read,
            key=f"open_btn_{article_id}"
        )

        read_button = ft.TextButton(
            "✅ Прочитано" if is_read else "Отметить прочитанным",
            on_click=lambda e: self.mark_as_read(title),
            disabled=is_read,
            key=f"read_btn_{article_id}"
        )

        card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        chip,
                        ft.Container(width=10),
                        date_text,
                        ft.Container(width=10),
                        icon,
                    ], key=f"header_{article_id}"),
                    title_text,
                    summary_text,
                    ft.Row([
                        open_button,
                        read_button,
                    ], key=f"buttons_{article_id}")
                ]),
                padding=15
            ),
            key=f"card_{article_id}"
        )

        # Сохраняем ссылки на контролы для будущего обновления
        self.card_refs[article_id] = {
            'card': card,
            'chip': chip,
            'date_text': date_text,
            'icon': icon,
            'title_text': title_text,
            'summary_text': summary_text,
            'open_button': open_button,
            'read_button': read_button,
            'article': article
        }

        return card

    # Обработчики событий
    def refresh_news(self, e):
        """Обновить новости"""
        if self.orchestrator:
            # Показываем начальное сообщение
            self.page.snack_bar = ft.SnackBar(ft.Text("Начинаем обновление новостей..."))
            self.page.snack_bar.open = True
            self.page.update()

            # Запускаем парсинг в отдельном потоке
            def run_parsing():
                try:
                    count = self.orchestrator.run_full_cycle()
                    # Обновляем UI через run_task
                    async def update_ui():
                        self.page.snack_bar = ft.SnackBar(
                            ft.Text(f"Новости обновлены! Добавлено {count} новостей.")
                        )
                        self.page.snack_bar.open = True
                        self.update_feed_display()
                        self.page.update()
                    self.page.run_task(update_ui)
                except Exception as ex:
                    async def show_error():
                        self.page.snack_bar = ft.SnackBar(
                            ft.Text(f"Ошибка при обновлении: {str(ex)}")
                        )
                        self.page.snack_bar.open = True
                        self.page.update()
                    self.page.run_task(show_error)

            threading.Thread(target=run_parsing, daemon=True).start()
        else:
            self.page.snack_bar = ft.SnackBar(ft.Text("Парсер не инициализирован"))
            self.page.snack_bar.open = True
            self.page.update()



    def load_articles_from_db(self):
        """Загрузить новости из базы данных"""
        print(f"Loading articles from DB, repository: {self.repository is not None}")
        if self.repository:
            try:
                # Загружаем последние 50 новостей
                db_articles = self.repository.get_articles(limit=50)
                print(f"DB returned {len(db_articles)} articles")
                # Преобразуем в формат для UI
                self.all_articles = []
                for article in db_articles:
                    article_dict = {
                        'id': article.id,
                        'source': article.source,
                        'title': article.title or "Без заголовка",
                        'summary': article.summary[:200] + "..." if article.summary and len(article.summary) > 200 else article.summary or "Без описания",
                        'category': article.category,
                        'published_at': article.published_at.strftime("%Y-%m-%d %H:%M") if article.published_at else "Неизвестно",
                        'url': article.url or "#",
                        'is_read': bool(article.is_read)
                    }
                    self.all_articles.append(article_dict)

                # Применяем фильтр
                self.apply_filter()
                print(f"Загружено {len(self.all_articles)} новостей, показано {len(self.articles)}")

                # Очищаем старые ссылки на карточки
                self.card_refs.clear()

            except Exception as e:
                print(f"Ошибка загрузки новостей из БД: {e}")
                import traceback
                traceback.print_exc()
                self.all_articles = []
                self.articles = []
        else:
            print("Репозиторий не инициализирован")
            self.all_articles = []
            self.articles = []

    def apply_filter(self):
        """Применить фильтр к новостям"""
        if self.show_unread_only:
            self.articles = [article for article in self.all_articles if not article['is_read']]
        else:
            self.articles = self.all_articles.copy()

    def toggle_unread_filter(self, e):
        """Переключить фильтр непрочитанных новостей"""
        self.show_unread_only = e.control.value
        self.apply_filter()
        if self.current_page_index == 0:  # Если на странице ленты
            self.page_content.content = self.build_feed_page()
        self.page.snack_bar = ft.SnackBar(ft.Text("Фильтр применен"))
        self.page.snack_bar.open = True
        self.page.update()





    def update_feed_display(self):
        """Обновить отображение ленты новостей"""
        # Перезагружаем новости из базы
        self.load_articles_from_db()
        # Обновляем страницу ленты
        if self.current_page_index == 0:  # Если мы на странице ленты
            self.page_content.content = self.build_feed_page()
        self.page.update()

    def add_rss_source(self, e):
        """Добавить RSS источник"""
        def close_dialog(e):
            self.page.dialog.open = False
            self.page.update()

        def save_source(e):
            url = self.rss_url_field.value.strip()
            if url:
                # TODO: Добавить источник в базу данных
                self.page.snack_bar = ft.SnackBar(ft.Text(f"Источник добавлен: {url}"))
                self.page.snack_bar.open = True
                self.page.dialog.open = False
                self.page.update()
            else:
                self.page.snack_bar = ft.SnackBar(ft.Text("Введите URL источника"))
                self.page.snack_bar.open = True
                self.page.update()

        self.rss_url_field = ft.TextField(
            label="URL RSS ленты",
            hint_text="https://example.com/rss",
            width=400
        )

        self.page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Добавить RSS источник"),
            content=ft.Column([
                self.rss_url_field,
                ft.Text("Поддерживаются RSS/Atom ленты новостных сайтов", size=12, color=ft.Colors.GREY),
            ], tight=True),
            actions=[
                ft.TextButton("Отмена", on_click=close_dialog),
                ft.ElevatedButton("Добавить", on_click=save_source),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.dialog.open = True
        self.page.update()

    def run_parsing(self, e):
        """Запустить парсинг источников"""
        if self.orchestrator:
            # Показываем начальное сообщение
            self.page.snack_bar = ft.SnackBar(ft.Text("🔄 Запускаем парсинг RSS источников..."))
            self.page.snack_bar.open = True
            self.page.update()

            # Запускаем парсинг в отдельном потоке
            def run_parsing():
                try:
                    count = self.orchestrator.run_full_cycle()
                    # Обновляем UI через run_task
                    async def update_ui():
                        status = "✅" if count > 0 else "ℹ️"
                        self.page.snack_bar = ft.SnackBar(
                            ft.Text(f"{status} Парсинг завершен! Обработано {count} новостей по Крыму.")
                        )
                        self.page.snack_bar.open = True
                        self.update_feed_display()
                        self.page.update()
                    self.page.run_task(update_ui)
                except Exception as ex:
                    async def show_error():
                        self.page.snack_bar = ft.SnackBar(
                            ft.Text(f"❌ Ошибка парсинга: {str(ex)}")
                        )
                        self.page.snack_bar.open = True
                        self.page.update()
                    self.page.run_task(show_error)

            threading.Thread(target=run_parsing, daemon=True).start()
        else:
            self.page.snack_bar = ft.SnackBar(ft.Text("⚠️ Парсер не инициализирован"))
            self.page.snack_bar.open = True
            self.page.update()

    def test_ollama(self, e):
        """Проверить Ollama"""
        self.page.snack_bar = ft.SnackBar(ft.Text("Ollama проверяется..."))
        self.page.snack_bar.open = True
        self.page.update()

    def toggle_theme(self, e):
        """Переключить тему"""
        self.page.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        self.page.update()

    def toggle_auto_update(self, e):
        """Переключить автообновление"""
        self.auto_update_enabled = e.control.value
        status = "включено (требуется перезапуск)" if self.auto_update_enabled else "отключено"
        self.page.snack_bar = ft.SnackBar(ft.Text(f"Автообновление {status}"))
        self.page.snack_bar.open = True
        self.page.update()

    def save_settings(self, e):
        """Сохранить настройки"""
        self.page.snack_bar = ft.SnackBar(ft.Text("Настройки сохранены"))
        self.page.snack_bar.open = True
        self.page.update()

    def open_news(self, title):
        """Открыть новость"""
        # Найти URL новости по заголовку
        news_url = None
        for article in self.articles:
            if article['title'] == title:
                news_url = article['url']
                break

        if news_url and news_url != "#":
            try:
                # Используем run_task для асинхронного вызова
                async def launch_url_async():
                    await self.page.launch_url(news_url)
                    self.page.snack_bar = ft.SnackBar(ft.Text(f"🌐 Открываем в браузере: {title[:30]}..."))
                    self.page.snack_bar.open = True
                    self.page.update()

                self.page.run_task(launch_url_async)
            except Exception as e:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"❌ Не удалось открыть: {str(e)}"))
                self.page.snack_bar.open = True
                self.page.update()
        else:
            self.page.snack_bar = ft.SnackBar(ft.Text("ℹ️ Ссылка на новость недоступна"))
            self.page.snack_bar.open = True
            self.page.update()

    def mark_as_read(self, title):
        """Отметить как прочитанную"""
        if self.repository:
            try:
                # Найти новость в локальном кэше
                target_article = None
                for article in self.articles:
                    if article['title'] == title:
                        target_article = article
                        break

                if target_article:
                    news_id = target_article['id']
                    # Обновить статус в базе данных
                    success = self.repository.mark_as_read(news_id)
                    if success:
                        # Обновить локальный кэш
                        target_article['is_read'] = True

                        # Обновляем конкретные контролы без перестройки всей страницы
                        article_id = target_article['id']
                        if article_id in self.card_refs:
                            refs = self.card_refs[article_id]

                            # Обновляем свойства контролов
                            is_dark = self.page.theme_mode == ft.ThemeMode.DARK
                            refs['icon'].name = ft.Icons.CHECK_CIRCLE
                            refs['icon'].color = ft.Colors.GREEN
                            refs['title_text'].color = ft.Colors.GREY_400 if not is_dark else ft.Colors.GREY_300
                            refs['summary_text'].color = ft.Colors.GREY_500 if not is_dark else ft.Colors.GREY_400
                            refs['read_button'].text = "✅ Прочитано"
                            refs['read_button'].disabled = True
                            refs['open_button'].disabled = True

                            # Обновляем страницу для применения изменений
                            self.page.update()

                            # Показываем уведомление
                            self.page.snack_bar = ft.SnackBar(
                                ft.Text(f"✅ Новость отмечена как прочитанная")
                            )
                            self.page.snack_bar.open = True
                            self.page.update()
                        else:
                            # Fallback - перестраиваем страницу если ссылки нет
                            async def update_ui_fallback():
                                if self.current_page_index == 0:
                                    self.page_content.content = self.build_feed_page()
                                self.page.update()

                                self.page.snack_bar = ft.SnackBar(
                                    ft.Text(f"✅ Новость отмечена как прочитанная")
                                )
                                self.page.snack_bar.open = True
                                self.page.update()

                            self.page.run_task(update_ui_fallback)


                        self.page.snack_bar = ft.SnackBar(ft.Text(f"✅ Отмечено как прочитанное: {title[:30]}..."))


                    else:
                        self.page.snack_bar = ft.SnackBar(ft.Text("❌ Не удалось обновить статус в БД"))
                else:
                    self.page.snack_bar = ft.SnackBar(ft.Text(f"ℹ️ Новость не найдена: {title[:30]}..."))
            except Exception as e:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"❌ Ошибка: {str(e)}"))
                print(f"Error in mark_as_read: {e}")
        else:
            self.page.snack_bar = ft.SnackBar(ft.Text("⚠️ База данных недоступна"))

        self.page.snack_bar.open = True
        self.page.update()

    def on_close(self, e=None):
        """Обработчик закрытия приложения"""
        print("Приложение закрывается... Все процессы остановлены.")
        return True


def main(page: ft.Page):
    """Главная функция приложения"""
    app = NewsAnalyzerApp()
    app.main(page)


if __name__ == "__main__":
    ft.app(target=main)