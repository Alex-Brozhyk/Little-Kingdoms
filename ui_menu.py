"""
Little Kingdoms — головне меню (Beta, ТЗ 2.1-2.2).

Фон — це сама гра: генерується випадкова мапа 44x14 (усі 4 типи води
рівноймовірні), розтягнута на всю висоту вікна без верхнього/нижнього
відступу, з 8 замками всіх кольорів. Мапа плавно "дихає" вліво-вправо
по синусоїді (без ривків на краях — синус сам дає плавне уповільнення
й розворот).

Технічна деталь: і анімований фон, і біла картка меню/Play-locally
живуть на ОДНОМУ tk.Canvas (self.canvas). Це важливо — якби картка
була окремим Canvas-віджетом, накладеним зверху через .place(), по її
заокруглених кутах було б видно прямокутну "пляму" замість мапи
(tkinter-віджети не бувають прозорими). Малюючи все на одному canvas,
ми просто лишаємо мапу непроторканою під заокругленими кутами картки.
Панорамування фону реалізоване через canvas.move(), а не через
xview_moveto() — так елементи картки (тег "menucard"/"setupcard"),
які не мають тегу мапи, ніколи не зсуваються разом з нею.

Кнопки Play through LAN / Map editor / Tutorial / Settings поки що
no-op заглушки (TODO) — до них повернемось на відповідних етапах ТЗ.
"""

import math
import random
import tkinter as tk

import graphics
import world_gen
from config import PLAYER_COLORS
from ui_setup import PlayLocallySetupPanel
from ui_widgets import CARD_COLOR, CARD_SHADOW, RoundedButton, draw_rounded_rect

# ---------------------------------------------------------------------------
# Анімований фон
# ---------------------------------------------------------------------------

BG_MAP_WIDTH = 24
BG_MAP_HEIGHT = 15
MIN_READY_SIZE = 300                   # чекаємо реального розміру вікна перед побудовою

# ---------------------------------------------------------------------------
# Кнопки головного меню: (текст, колір, колір при наведенні, колір тексту, обробник)
# ---------------------------------------------------------------------------

MENU_BUTTONS = [
    ("Play locally", "#27ae60", "#2ecc71", "white", "_on_play_locally"),
    ("Play trow LAN", "#27ae60", "#2ecc71", "white", "_on_play_lan"),
    ("Map editor", "#8e44ad", "#9b59b6", "white", "_on_map_editor"),
    ("Tutorial", "#3498db", "#5dade2", "white", "_on_tutorial"),
    ("Settings", "#f1c40f", "#f4d03f", "#2c3e50", "_on_settings"),
    ("Exit", "#c0392b", "#e74c3c", "white", "_on_exit"),
]


class MenuScreen(tk.Frame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, bg="#000000", **kwargs)
        self.app = app

        self._bg_ready = False
        
        self._setup_panel = None
        self._setup_overlay_ids = []

        self.canvas = tk.Canvas(self, highlightthickness=0, bg="#00cc00")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind("<Destroy>", self._on_destroy)

    # ------------------------------------------------------------------
    # Перша (і єдина) побудова, щойно відомий реальний розмір вікна
    # ------------------------------------------------------------------
    def _on_canvas_configure(self, event):
        if self._bg_ready or event.width < MIN_READY_SIZE or event.height < MIN_READY_SIZE:
            return
        self._bg_ready = True
        self._build_background(event.width, event.height)
        self._build_main_menu_card(event.width, event.height)
        self._animate_background()

    def _on_destroy(self, event):
        if event.widget is self and self._anim_job is not None:
            self.after_cancel(self._anim_job)
            self._anim_job = None

    # ------------------------------------------------------------------
    # Анімований фон-мапа
    # ------------------------------------------------------------------
    def _build_background(self, viewport_w, viewport_h):
        water_mode = random.choice([
            world_gen.WATER_MODE_NONE, world_gen.WATER_MODE_RIVERS,
            world_gen.WATER_MODE_LAKES, world_gen.WATER_MODE_ISLANDS,
        ])
        grid = world_gen.generate_world(BG_MAP_WIDTH, BG_MAP_HEIGHT, water_mode)

        demo_players = [{"id": i, "color": name} for i, name in enumerate(PLAYER_COLORS)]
        castles = world_gen.place_castles(grid, BG_MAP_WIDTH, BG_MAP_HEIGHT, demo_players)

        tile_size = viewport_h / BG_MAP_HEIGHT
        map_px_width = BG_MAP_WIDTH * tile_size
        self._max_pan = max(0.0, map_px_width - viewport_w)

        for row in range(BG_MAP_HEIGHT):
            for col in range(BG_MAP_WIDTH):
                x1, y1 = col * tile_size, row * tile_size
                graphics.draw_tile(self.canvas, x1, y1, x1 + tile_size, y1 + tile_size, grid[row][col])

        for castle in castles:
            x1 = castle["col"] * tile_size
            y1 = castle["row"] * tile_size
            color_hex = PLAYER_COLORS[castle["color"]]
            graphics.draw_castle(self.canvas, x1, y1, x1 + tile_size, y1 + tile_size, color_hex)

        # Усе, що вже намальоване на цьому етапі (тайли + замки) і є фоном —
        # тегуємо одним тегом, щоб панорамувати одним викликом canvas.move().
        self.canvas.addtag_withtag("bgmap", "all")


    # ------------------------------------------------------------------
    # Головна картка меню (заголовок + 6 кнопок)
    # ------------------------------------------------------------------
    def _build_main_menu_card(self, viewport_w, viewport_h):
        # Без pack_propagate(False): картка сама підганяє висоту під 6
        # кнопок, а ширина й так контролюється фіксованою шириною кнопок.
        body = tk.Frame(self.canvas, bg=CARD_COLOR)

        tk.Label(body, text="Little Kingdoms", bg=CARD_COLOR, fg="#2c3e50",
                 font=("Arial", 24, "bold")).pack(pady=(22, 14))

        for label, bg, hover_bg, fg, handler_name in MENU_BUTTONS:
            RoundedButton(
                body, text=label, command=getattr(self, handler_name),
                width=260, height=54, radius=16, bg=bg, hover_bg=hover_bg, fg=fg,
                font=("Arial", 15, "bold"),
            ).pack(pady=8)

        tk.Frame(body, bg=CARD_COLOR, height=10).pack()

        body.update_idletasks()
        w, h = body.winfo_reqwidth(), body.winfo_reqheight()
        cx, cy = viewport_w / 2, viewport_h / 2

        draw_rounded_rect(self.canvas, cx - w / 2 - 4, cy - h / 2 + 6, cx + w / 2 + 4, cy + h / 2 + 10,
                           28, fill=CARD_SHADOW, outline="", tags="menucard")
        draw_rounded_rect(self.canvas, cx - w / 2 - 10, cy - h / 2 - 10, cx + w / 2 + 10, cy + h / 2 + 10,
                           28, fill=CARD_COLOR, outline="", tags="menucard")
        self.canvas.create_window(cx, cy, window=body, tags="menucard")

    # ------------------------------------------------------------------
    # Play locally — заокруглена картка налаштувань поверх меню
    # ------------------------------------------------------------------
    def _on_play_locally(self):
        if self._setup_panel is not None:
            return

        self._setup_panel = PlayLocallySetupPanel(self.canvas, app=self.app, on_close=self._close_setup)
        self._setup_panel.update_idletasks()
        w, h = self._setup_panel.winfo_reqwidth(), self._setup_panel.winfo_reqheight()

        cx, cy = self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2

        shadow_id = draw_rounded_rect(
            self.canvas, cx - w / 2 - 4, cy - h / 2 + 6, cx + w / 2 + 4, cy + h / 2 + 10,
            28, fill=CARD_SHADOW, outline="",
        )
        bg_id = draw_rounded_rect(
            self.canvas, cx - w / 2 - 10, cy - h / 2 - 10, cx + w / 2 + 10, cy + h / 2 + 10,
            28, fill=CARD_COLOR, outline="",
        )
        window_id = self.canvas.create_window(cx, cy, window=self._setup_panel)

        self._setup_overlay_ids = [shadow_id, bg_id, window_id]

    def _close_setup(self):
        if self._setup_panel is None:
            return
        for item_id in self._setup_overlay_ids:
            self.canvas.delete(item_id)
        self._setup_panel.destroy()
        self._setup_panel = None
        self._setup_overlay_ids = []

    # ------------------------------------------------------------------
    # Інші кнопки меню — заглушки до відповідних фаз ТЗ
    # ------------------------------------------------------------------
    def _on_play_lan(self):
        pass  # TODO: LAN UI (Host/Join) — перевикористає PlayLocallySetupPanel + мережеві поля

    def _on_map_editor(self):
        pass  # TODO: Map Creator (ТЗ 2.5)

    def _on_tutorial(self):
        pass  # TODO: Tutorial-мапа + підказки бота (ТЗ 2.6)

    def _on_settings(self):
        pass  # TODO: Animations/No animations, гучність звуку/музики (ТЗ 2.7)

    def _on_exit(self):
        self.app.destroy()
