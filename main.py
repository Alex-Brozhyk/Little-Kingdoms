"""
Little Kingdoms — головна точка запуску гри.

Цей файл відповідає лише за життєвий цикл вікна застосунку:
створення повноекранного вікна, яке динамічно масштабується,
та перемикання між екранами (головне меню / гра). Уся логіка
конкретних екранів винесена в окремі модулі (ui_menu.py, ui_game.py),
які підключаються на наступних кроках розробки.
"""

import tkinter as tk

from ui_menu import MenuScreen
from ui_game import GameScreen


class LittleKingdomsApp(tk.Tk):
    """Кореневе вікно застосунку та менеджер екранів.

    Реалізує патерн "контейнер + екрани": в один і той самий контейнер
    по черзі монтуються різні Frame-екрани (головне меню, ігрове поле
    тощо), а попередній екран знищується. Це дає змогу перемикатися
    між екранами без відкриття нових вікон, і саме на цьому контейнері
    базуватиметься динамічне масштабування ігрового поля.
    """

    def __init__(self):
        super().__init__()
        self.title("Little Kingdoms")

        self._current_screen = None
        self._is_fullscreen = True

        self._configure_window()
        self._build_container()
        self._bind_hotkeys()

        self.show_screen(MenuScreen)

    # ------------------------------------------------------------------
    # Налаштування вікна
    # ------------------------------------------------------------------
    def _configure_window(self):
        """Розгортає вікно на весь екран і дозволяє його масштабування."""
        self.configure(bg="#1e272c")
        self.attributes("-fullscreen", self._is_fullscreen)
        self.resizable(True, True)

    def _build_container(self):
        """Створює контейнер, у якому монтуються екрани.

        Контейнер завжди займає весь простір вікна й автоматично
        підлаштовується під його розмір.
        """
        self.container = tk.Frame(self, bg="#1e272c")
        self.container.pack(fill="both", expand=True)

    def _bind_hotkeys(self):
        """Прив'язує клавіші керування вікном."""
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Escape>", self._exit_fullscreen)

    def _toggle_fullscreen(self, event=None):
        self._is_fullscreen = not self._is_fullscreen
        self.attributes("-fullscreen", self._is_fullscreen)

    def _exit_fullscreen(self, event=None):
        """Вихід із повноекранного режиму в звичайне (розтягуване) вікно."""
        if self._is_fullscreen:
            self._is_fullscreen = False
            self.attributes("-fullscreen", False)
            self.geometry("1280x800")

    # ------------------------------------------------------------------
    # Керування екранами
    # ------------------------------------------------------------------
    def show_screen(self, screen_class, **kwargs):
        """Знищує поточний екран і монтує новий у контейнер.

        Кожен майбутній екран (MenuScreen, GameScreen) має бути
        нащадком tk.Frame і приймати іменований аргумент app=self,
        щоб мати змогу викликати app.show_screen(...) для переходу далі
        (наприклад, з меню в гру).
        """
        if self._current_screen is not None:
            self._current_screen.destroy()

        self._current_screen = screen_class(self.container, app=self, **kwargs)
        self._current_screen.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Callback-и, які викликають екрани
    # ------------------------------------------------------------------
    def on_menu_confirmed(self, settings):
        """Викликається з MenuScreen, коли гравець коректно заповнив меню.

        Переходить на ігровий екран з обраними налаштуваннями
        (розмір мапи, тип води, список гравців).
        """
        self.show_screen(GameScreen, settings=settings)


def main():
    app = LittleKingdomsApp()
    app.mainloop()


if __name__ == "__main__":
    main()
