"""
Little Kingdoms — ігровий екран (Beta).

Клік на клітинку одночасно виділяє і власний юніт, і власну будівлю,
якщо обидва там є — тоді в нижній панелі показуються ОБИДВА набори
кнопок окремими групами (як в Alpha).

Нове в Beta:
  - Підказка ціни/AP більше НЕ спливаюче вікно — це смужка над кнопками
    нижньої панелі (info-strip), яка оновлюється при наведенні й показує
    вартість іконками ресурсів (щоб узгоджуватись із рештою UI).
  - Недоступні дії (не вистачає ресурсів/технології/AP/House/Horse) —
    кнопка лишається на місці, але сіра, з червоним "заблоковано" поверх
    іконки; наведення все одно показує причину в info-strip.
  - Плавні анімації: рух (юніт "з'їжджає" на нову клітинку, не
    телепортується), ближній бій (випад + спалах на цілі), дальня атака
    й заклинання (снаряд/іскра летить від юніта до цілі), будівництво/
    ремонт/прокачка (пульсація на клітинці). Стан гри мутується одразу
    (game_logic синхронний) — анімація лише "наздоганяє" візуально.
  - Чат: працює в Local (по черзі — може писати лише активний гравець),
    але шлях відправки (_send_chat_message) навмисно єдина точка входу,
    щоб пізніше просто підключити LAN замість локального append.
  - House і Horse — кольором (зелений/червоний) показують, чи є ще місце.

Гарячі клавіші: Enter — End Turn, Esc — скасувати режим/вийти в меню,
W — найняти робітника, S/A/D/W/Q — Мечник/Спис/Булава/Лучник/Вершник
(в казармі), Q/W/E — висадка пасажира 1/2/3, R — ремонт, Z — знесення,
G — Go Inside, C — заклинання (маг обраний), 1-6 — обмін у Порту,
H/T/L/M/F/B/N/P/S/V/G — будівництво.
"""

import math
import tkinter as tk
from tkinter import messagebox

import config
import graphics
from world_gen import generate_world, place_castles, TILE_WATER
from game_logic import GameState
from models import ResourceBuilding, Tower
from ui_menu import MenuScreen
from ui_widgets import RoundedButton, CARD_COLOR

TOP_BAR_HEIGHT = 64
BOTTOM_BAR_HEIGHT = 232
INFO_STRIP_HEIGHT = 30

TOP_BAR_BG = "#16324f"
BOTTOM_BAR_BG = "#132840"
CANVAS_BG = "#1e272c"
SLOT_BG = "#0e1c2c"
INFO_STRIP_BG = "#0e1c2c"

HIGHLIGHT_COLORS = {
    "attack": "#e74c3c",
    "ranged_attack": "#e74c3c",
    "enter_resource": "#3498db",
    "board_ship": "#1abc9c",
    "barracks": "#9b59b6",
    "magic_school": "#9b59b6",
    "repair": "#f39c12",
    "steal": "#f1c40f",
}

SELECTABLE_BUILDING_KINDS = {
    "Castle", "House", "LumberMill", "Mill", "Mine", "Tower", "Port", "Barracks",
    "Smithy", "HorseStable", "MagicSchool",
}

BUILDING_LABELS = {
    "House": "House (H)", "LumberMill": "Lumber Mill (L)", "Mill": "Farm (F)", "Mine": "Mine (M)",
    "Barracks": "Barracks (B)", "Tower": "Tower (T)", "Port": "Port (P)", "Bridge": "Bridge (N)",
    "Smithy": "Smithy (S)", "HorseStable": "Horse Barn (V)", "MagicSchool": "Magic School (G)",
}

BARRACKS_UNIT_HOTKEY = {v: k.upper() for k, v in config.KEY_TO_BARRACKS_UNIT.items()}
TOWER_UPGRADE_HOTKEY = {v: k.upper() for k, v in config.TOWER_UPGRADE_HOTKEYS.items()}
SMITHY_TECH_HOTKEY = {v: k.upper() for k, v in config.SMITHY_TECH_HOTKEYS.items()}

FARM_ANIM_INTERVAL_MS = 700
CAMERA_KEY_SPEED = 8.0    # клітинок/сек при утриманні стрілки
CAMERA_KEY_TICK_MS = 30


def _format_cost(cost, ap=None, extra=None):
    parts = []
    if cost:
        if cost.get("gold"):
            parts.append(f"{cost['gold']}g")
        if cost.get("wood"):
            parts.append(f"{cost['wood']}w")
        if cost.get("food"):
            parts.append(f"{cost['food']}f")
    text = " ".join(parts) if parts else "Free"
    if ap is not None:
        text += f" · {ap} AP"
    if extra:
        text += f" · {extra}"
    return text


class GameScreen(tk.Frame):
    def __init__(self, master, app, settings, **kwargs):
        super().__init__(master, bg=CANVAS_BG, **kwargs)
        self.app = app
        self.settings = settings

        self.grid_cols = settings["map_width"]
        self.grid_rows = settings["map_height"]
        grid = generate_world(self.grid_cols, self.grid_rows, settings["water_mode"])
        castle_specs = place_castles(grid, self.grid_cols, self.grid_rows, settings["players"])

        self.state = GameState(grid, settings["players"])
        for spec in castle_specs:
            self.state.place_castle(spec["owner_id"], spec["row"], spec["col"])
        self.state.begin_game()
        self.grid = grid

        self.selected_unit_id = None
        self.selected_building_id = None
        self.mode = "idle"
        self.mode_context = {}

        self.tile_size = 10
        self.offset_x = 0
        self.offset_y = 0
        self._resize_job = None

        # Камера: zoom 0.0 = видно всю мапу, 1.0 = видно 8x8 клітинок.
        self.zoom = 0.0
        self.cam_row = 0.0
        self.cam_col = 0.0
        self._pan_start = None
        self._camera_anim_job = None
        self._camera_keys_held = set()
        self._camera_key_job = None

        self._farm_anim_frame = 0
        self._anim_job = None      # активна тимчасова анімація (рух/атака/etc.)
        self._tick_job = None

        self.chat_log = []
        self.chat_visible = False

        self._build_top_bar()
        self._build_canvas_area()
        self._build_bottom_bar()
        self._build_chat_panel()

        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_canvas_hover)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)
        self.canvas.bind("<ButtonPress-3>", self._on_pan_press)
        self.canvas.bind("<B3-Motion>", self._on_pan_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_pan_release)
        self.bind("<Key>", self._on_key_press)
        self.bind("<KeyRelease>", self._on_key_release)
        self.bind("<Destroy>", self._on_destroy)
        self.focus_set()

        self._refresh_top_bar()
        self._refresh_bottom_bar()
        self._tick()

    # ------------------------------------------------------------------
    def _on_destroy(self, event):
        if event.widget is not self:
            return
        for job in (self._camera_anim_job, self._camera_key_job, self._anim_job, self._tick_job, self._resize_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except (ValueError, tk.TclError):
                    pass

    def _tick(self):
        """Загальний таймер: анімація ферми (2 кадри) + утримувані стрілки камери."""
        self._farm_anim_frame = 1 - self._farm_anim_frame
        if self._camera_keys_held:
            self._apply_camera_key_pan()
        else:
            self._render_map()
        self._tick_job = self.after(FARM_ANIM_INTERVAL_MS, self._tick)

    # ------------------------------------------------------------------
    # Верхня панель — ресурси з іконками, House/Horse кольором ліміту
    # ------------------------------------------------------------------
    def _build_top_bar(self):
        bar = tk.Frame(self, bg=TOP_BAR_BG, height=TOP_BAR_HEIGHT)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)

        left = tk.Frame(bar, bg=TOP_BAR_BG)
        left.pack(side="left", padx=18)
        tk.Label(left, text="Turn:", fg="white", bg=TOP_BAR_BG, font=("Arial", 15, "bold")).pack(side="left")
        self.turn_value_label = tk.Label(left, text="", bg=TOP_BAR_BG, font=("Arial", 15, "bold"))
        self.turn_value_label.pack(side="left", padx=(6, 0))

        mid = tk.Frame(bar, bg=TOP_BAR_BG)
        mid.pack(side="left", expand=True)

        self.gold_value = self._build_resource_readout(mid, graphics.draw_icon_gold)
        self.wood_value = self._build_resource_readout(mid, graphics.draw_icon_wood)
        self.food_value = self._build_resource_readout(mid, graphics.draw_icon_food)
        self.house_value = self._build_resource_readout(mid, self._house_icon_func())
        self.horse_value = self._build_resource_readout(mid, self._horse_icon_func())

        RoundedButton(
            bar, text="Chat", command=self._toggle_chat,
            width=90, height=40, bg="#2c4c6b", hover_bg="#3a5f85", font=("Arial", 11, "bold"),
        ).pack(side="right", padx=(0, 10))
        RoundedButton(
            bar, text="Exit to Menu (Esc)", command=self._on_exit_clicked,
            width=180, height=44, bg="#c0392b", hover_bg="#e74c3c", font=("Arial", 12, "bold"),
        ).pack(side="right", padx=10)

    def _house_icon_func(self):
        def draw(canvas, x1, y1, x2, y2):
            color_hex = config.PLAYER_COLORS.get(self.state.current_player().color, "#fff")
            graphics.draw_house(canvas, x1, y1, x2, y2, color_hex)
        return draw

    def _horse_icon_func(self):
        def draw(canvas, x1, y1, x2, y2):
            color_hex = config.PLAYER_COLORS.get(self.state.current_player().color, "#fff")
            graphics.draw_icon_horse(canvas, x1, y1, x2, y2, color_hex)
        return draw

    def _build_resource_readout(self, parent, icon_draw_func):
        cell = tk.Frame(parent, bg=TOP_BAR_BG)
        cell.pack(side="left", padx=10)
        icon = tk.Canvas(cell, width=26, height=26, bg=TOP_BAR_BG, highlightthickness=0)
        icon.pack(side="left")
        icon_draw_func(icon, 2, 2, 24, 24)
        value = tk.Label(cell, text="", fg="white", bg=TOP_BAR_BG, font=("Arial", 13, "bold"))
        value.pack(side="left", padx=(4, 0))
        return value

    def _refresh_top_bar(self):
        current = self.state.current_player()
        color_hex = config.PLAYER_COLORS.get(current.color, "#ffffff")
        self.turn_value_label.configure(text=current.color, fg=color_hex)

        res = current.resources
        gains = self.state.preview_next_gain(current.id)
        self.gold_value.configure(text=f"{res['gold']} (+{gains['gold']})")
        self.wood_value.configure(text=f"{res['wood']} (+{gains['wood']})")
        self.food_value.configure(text=f"{res['food']} (+{gains['food']})")

        house_used, house_limit = self.state.house_used(current.id), self.state.house_limit(current.id)
        horse_used, horse_limit = self.state.horse_used(current.id), self.state.horse_limit(current.id)
        self.house_value.configure(
            text=f"{house_used}/{house_limit}",
            fg=("#e74c3c" if house_used >= house_limit else "#2ecc71"),
        )
        self.horse_value.configure(
            text=f"{horse_used}/{horse_limit}",
            fg=("#e74c3c" if horse_limit > 0 and horse_used >= horse_limit else
                ("#7f8c8d" if horse_limit == 0 else "#2ecc71")),
        )

    # ------------------------------------------------------------------
    # Центральна карта + камера (зум/панорама/плавні стрілки)
    # ------------------------------------------------------------------
    def _build_canvas_area(self):
        container = tk.Frame(self, bg=CANVAS_BG)
        container.pack(side="top", fill="both", expand=True)
        self._canvas_container = container

        self.zoom_slider = tk.Scale(
            container, from_=1.0, to=0.0, resolution=0.01, orient="vertical",
            showvalue=False, bg=CANVAS_BG, troughcolor="#0e1c2c", highlightthickness=0,
            sliderlength=28, width=14, command=self._on_zoom_slider_change,
        )
        self.zoom_slider.set(0.0)
        self.zoom_slider.pack(side="left", fill="y", padx=(6, 2), pady=8)

        self.canvas = tk.Canvas(container, bg=CANVAS_BG, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

    def _visible_span(self):
        min_cols = min(8, self.grid_cols)
        min_rows = min(8, self.grid_rows)
        visible_cols = self.grid_cols - self.zoom * (self.grid_cols - min_cols)
        visible_rows = self.grid_rows - self.zoom * (self.grid_rows - min_rows)
        return visible_cols, visible_rows

    def _clamp_camera(self):
        visible_cols, visible_rows = self._visible_span()
        max_col = max(0.0, self.grid_cols - visible_cols)
        max_row = max(0.0, self.grid_rows - visible_rows)
        self.cam_col = min(max(0.0, self.cam_col), max_col)
        self.cam_row = min(max(0.0, self.cam_row), max_row)

    def _visible_tile_range(self):
        visible_cols, visible_rows = self._visible_span()
        col_start = max(0, int(math.floor(self.cam_col)))
        row_start = max(0, int(math.floor(self.cam_row)))
        col_end = min(self.grid_cols, int(math.ceil(self.cam_col + visible_cols)) + 1)
        row_end = min(self.grid_rows, int(math.ceil(self.cam_row + visible_rows)) + 1)
        return row_start, row_end, col_start, col_end

    def _on_canvas_resize(self, event):
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(40, self._recompute_layout_and_render)

    def _recompute_layout_and_render(self):
        self._resize_job = None
        avail_w = self.canvas.winfo_width()
        avail_h = self.canvas.winfo_height()
        if avail_w <= 1 or avail_h <= 1:
            return
        visible_cols, visible_rows = self._visible_span()
        self.tile_size = max(1e-6, min(avail_w / visible_cols, avail_h / visible_rows))
        self.offset_x = (avail_w - self.tile_size * visible_cols) / 2
        self.offset_y = (avail_h - self.tile_size * visible_rows) / 2
        self._clamp_camera()
        self._render_map()

    def _on_zoom_slider_change(self, value):
        self.zoom = float(value)
        self._recompute_layout_and_render()

    def _on_mouse_wheel(self, event):
        step = 0.05
        if getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0:
            step = -0.05
        world_col = self.cam_col + (event.x - self.offset_x) / self.tile_size
        world_row = self.cam_row + (event.y - self.offset_y) / self.tile_size
        self.zoom = min(1.0, max(0.0, self.zoom + step))
        self.zoom_slider.set(self.zoom)
        self._recompute_layout_and_render()
        self.cam_col = world_col - (event.x - self.offset_x) / self.tile_size
        self.cam_row = world_row - (event.y - self.offset_y) / self.tile_size
        self._clamp_camera()
        self._render_map()

    def _on_pan_press(self, event):
        self._pan_start = (event.x, event.y, self.cam_col, self.cam_row)

    def _on_pan_drag(self, event):
        if self._pan_start is None:
            return
        start_x, start_y, start_col, start_row = self._pan_start
        self.cam_col = start_col - (event.x - start_x) / self.tile_size
        self.cam_row = start_row - (event.y - start_y) / self.tile_size
        self._clamp_camera()
        self._render_map()

    def _on_pan_release(self, event):
        self._pan_start = None

    def _apply_camera_key_pan(self):
        """Плавна прокрутка стрілками — безперервний рух, поки клавішу
        утримують, а не миттєвий стрибок на клітинку (ТЗ 3.1)."""
        dt = CAMERA_KEY_TICK_MS / 1000
        step = CAMERA_KEY_SPEED * dt
        if "Left" in self._camera_keys_held:
            self.cam_col -= step
        if "Right" in self._camera_keys_held:
            self.cam_col += step
        if "Up" in self._camera_keys_held:
            self.cam_row -= step
        if "Down" in self._camera_keys_held:
            self.cam_row += step
        self._clamp_camera()
        self._render_map()

    def _tile_rect(self, row, col):
        ts = self.tile_size
        x1 = self.offset_x + (col - self.cam_col) * ts
        y1 = self.offset_y + (row - self.cam_row) * ts
        return x1, y1, x1 + ts, y1 + ts

    # ------------------------------------------------------------------
    # Рендер мапи
    # ------------------------------------------------------------------
    def _bridge_orientation(self, row, col):
        def is_water(r, c):
            return 0 <= r < self.grid_rows and 0 <= c < self.grid_cols and self.grid[r][c] == TILE_WATER

        horiz = is_water(row, col - 1) or is_water(row, col + 1)
        vert = is_water(row - 1, col) or is_water(row + 1, col)
        if horiz and vert:
            return "cross"
        return "vertical" if horiz else "horizontal"

    def _draw_building_at(self, canvas, building, x1, y1, x2, y2):
        color_hex = config.PLAYER_COLORS.get(self.state.players[building.owner_id].color, "#888888")
        techs = self.state.players[building.owner_id].researched_techs
        if isinstance(building, Tower):
            graphics.draw_tower(canvas, x1, y1, x2, y2, color_hex,
                                 tower_type=building.tower_type, armored=("ArmoredTowers" in techs))
        elif building.kind == "Bridge":
            graphics.draw_bridge(canvas, x1, y1, x2, y2,
                                  orientation=self._bridge_orientation(building.row, building.col))
        elif building.kind == "UnderConstruction":
            graphics.draw_under_construction(canvas, x1, y1, x2, y2, color_hex)
        elif building.kind == "Mill":
            graphics.draw_farm(canvas, x1, y1, x2, y2, color_hex, frame=self._farm_anim_frame)
        else:
            graphics.draw_building(canvas, x1, y1, x2, y2, building.kind, color_hex)

    def _draw_unit_at(self, canvas, unit, x1, y1, x2, y2):
        color_hex = config.PLAYER_COLORS.get(self.state.players[unit.owner_id].color, "#888888")
        techs = self.state.players[unit.owner_id].researched_techs
        k = unit.kind
        if k == "Worker":
            graphics.draw_worker(canvas, x1, y1, x2, y2, color_hex, action_points=unit.action_points)
        elif k == "Warrior":
            graphics.draw_warrior(
                canvas, x1, y1, x2, y2, color_hex, unit.warrior_type, action_points=unit.action_points,
                shield=(unit.warrior_type == "Sword" and "Shields" in techs),
                better_mace=(unit.warrior_type == "Mace" and "BetterMaces" in techs),
                alebard=(unit.warrior_type == "Spear" and "Alebards" in techs),
            )
        elif k == "Archer":
            graphics.draw_archer(canvas, x1, y1, x2, y2, color_hex, action_points=unit.action_points,
                                  crossbow=("Crossbow" in techs))
        elif k == "Horseman":
            graphics.draw_horseman(canvas, x1, y1, x2, y2, color_hex, action_points=unit.action_points,
                                    has_faster_horses=("FasterHorses" in techs))
        elif k == "Mage":
            graphics.draw_mage(canvas, x1, y1, x2, y2, color_hex, action_points=unit.action_points)
        elif k == "Slime":
            graphics.draw_slime(canvas, x1, y1, x2, y2, color_hex, action_points=unit.action_points)
        elif k == "Catapult":
            graphics.draw_catapult(canvas, x1, y1, x2, y2, color_hex)
        elif k == "Ship":
            graphics.draw_ship(canvas, x1, y1, x2, y2, color_hex, tired=unit.tired)
        elif k == "CannonBoat":
            graphics.draw_cannon_boat(canvas, x1, y1, x2, y2, color_hex)

    def _render_map(self):
        self.canvas.delete("all")
        team_color = config.PLAYER_COLORS.get(self.state.current_player().color, "#f1c40f")
        row_start, row_end, col_start, col_end = self._visible_tile_range()

        def in_view(r, c):
            return row_start <= r < row_end and col_start <= c < col_end

        for r in range(row_start, row_end):
            for c in range(col_start, col_end):
                x1, y1, x2, y2 = self._tile_rect(r, c)
                graphics.draw_tile(self.canvas, x1, y1, x2, y2, self.grid[r][c])

        for b in self.state.buildings.values():
            if not in_view(b.row, b.col):
                continue
            x1, y1, x2, y2 = self._tile_rect(b.row, b.col)
            self._draw_building_at(self.canvas, b, x1, y1, x2, y2)
            if isinstance(b, ResourceBuilding):
                graphics.draw_count_badge(self.canvas, x1, y1, x2, y2, len(b.workers_inside), b.capacity)
            graphics.draw_hp_bar(self.canvas, x1, y1, x2, y2, b.hp, b.max_hp)

        for (r, c), unit_id in self.state.unit_pos.items():
            if not in_view(r, c):
                continue
            u = self.state.units[unit_id]
            x1, y1, x2, y2 = self._tile_rect(r, c)
            self._draw_unit_at(self.canvas, u, x1, y1, x2, y2)
            if u.kind == "Ship":
                graphics.draw_count_badge(self.canvas, x1, y1, x2, y2, len(u.passengers), config.SHIP_CAPACITY)
            graphics.draw_hp_bar(self.canvas, x1, y1, x2, y2, u.hp, u.max_hp)

        for (r, c), kind in self._current_highlights().items():
            if not in_view(r, c):
                continue
            x1, y1, x2, y2 = self._tile_rect(r, c)
            color = team_color if kind == "move" else HIGHLIGHT_COLORS.get(kind, "#ffffff")
            self.canvas.create_rectangle(x1 + 2, y1 + 2, x2 - 2, y2 - 2, outline=color, width=3)

        sel_pos = self._selected_position()
        if sel_pos is not None and in_view(*sel_pos):
            x1, y1, x2, y2 = self._tile_rect(*sel_pos)
            self.canvas.create_rectangle(x1 + 1, y1 + 1, x2 - 1, y2 - 1, outline=team_color, width=4)

    def _selected_position(self):
        if self.selected_unit_id is not None and self.selected_unit_id in self.state.units:
            u = self.state.units[self.selected_unit_id]
            if self.state.unit_pos.get((u.row, u.col)) == u.id:
                return (u.row, u.col)
        if self.selected_building_id is not None and self.selected_building_id in self.state.buildings:
            b = self.state.buildings[self.selected_building_id]
            return (b.row, b.col)
        return None

    # ------------------------------------------------------------------
    # Підсвітка доступних клітинок
    # ------------------------------------------------------------------
    def _current_highlights(self):
        ctx = self.mode_context
        if self.mode == "hire_spawn":
            return {pos: "move" for pos in self.state.get_hire_spawn_tiles(ctx["building_id"])}
        if self.mode == "withdraw_worker":
            return {pos: "move" for pos in self.state.get_withdraw_tiles(ctx["building_id"])}
        if self.mode == "repair_target":
            highlights = {}
            for kind, tid in self.state.get_repairable_targets(ctx["worker_id"]):
                entity = self.state.buildings[tid] if kind == "building" else self.state.units[tid]
                highlights[(entity.row, entity.col)] = "repair"
            return highlights
        if self.mode == "build_tile":
            return {pos: "move" for pos in self.state.get_buildable_tiles(ctx["worker_id"], ctx["kind"])}
        if self.mode == "ship_spawn":
            return {pos: "move" for pos in self.state.get_ship_spawn_tiles(ctx["port_id"])}
        if self.mode == "cannon_boat_spawn":
            return {pos: "move" for pos in self.state.get_ship_spawn_tiles(ctx["port_id"])}
        if self.mode == "catapult_spawn":
            return {pos: "move" for pos in self.state.get_catapult_spawn_tiles(ctx["smithy_id"])}
        if self.mode == "disembark":
            return {pos: "move" for pos in self.state.get_disembark_tiles(ctx["ship_id"])}
        if self.mode == "ranged_target":
            return dict(self.state.get_ranged_attack_tiles(ctx["unit_id"]))
        if self.mode == "cannon_boat_move":
            highlights = {pos: "move" for pos in self.state.get_cannon_boat_reachable_tiles(ctx["boat_id"])}
            highlights.update(self.state.get_ranged_attack_tiles(ctx["boat_id"]))
            return highlights
        if self.mode == "spell_target":
            return {pos: "steal" for pos in self.state.get_spell_target_tiles(ctx["mage_id"], ctx["spell_name"])}
        if self.mode == "spell_teleport_destination":
            return {pos: "enter_resource" for pos in
                    self.state.get_teleport_destination_tiles(ctx["mage_id"], ctx["unit_row"], ctx["unit_col"])}
        if self.mode in ("barracks_choice", "magic_school_choice", "tower_upgrade_choice", "spell_choice"):
            pos = ctx.get("anchor_pos")
            return {pos: "barracks"} if pos else {}

        if (self.mode == "idle" and self.selected_unit_id is not None
                and self.selected_unit_id in self.state.units):
            u = self.state.units[self.selected_unit_id]
            if u.owner_id != self.state.current_player_id:
                return {}
            if u.kind == "Ship":
                if u.tired:
                    return {}
                return {pos: "move" for pos in self.state.get_ship_reachable_tiles(u.id)}
            if u.kind == "CannonBoat":
                highlights = {pos: "move" for pos in self.state.get_cannon_boat_reachable_tiles(u.id)}
                highlights.update(self.state.get_ranged_attack_tiles(u.id))
                return highlights
            if self.state._is_exhausted(u):
                return {}
            highlights = dict(self.state.get_valid_interactions(u.id))
            if u.kind in ("Archer", "Catapult"):
                highlights.update(self.state.get_ranged_attack_tiles(u.id))
            return highlights
        return {}

    # ------------------------------------------------------------------
    # Клік по карті
    # ------------------------------------------------------------------
    def _on_canvas_hover(self, event):
        pass  # зарезервовано під підсвітку клітинки під курсором, якщо знадобиться

    def _on_canvas_click(self, event):
        self.focus_set()
        if self.tile_size <= 0 or self.state.current_player().is_bot or self.state.game_over:
            return

        col = int(math.floor(self.cam_col + (event.x - self.offset_x) / self.tile_size))
        row = int(math.floor(self.cam_row + (event.y - self.offset_y) / self.tile_size))

        if not (0 <= row < self.grid_rows and 0 <= col < self.grid_cols):
            if self.mode != "idle":
                self._cancel_mode()
            else:
                self._clear_selection()
                self._render_map()
                self._refresh_bottom_bar()
            return

        if self.mode in ("barracks_choice", "magic_school_choice", "tower_upgrade_choice", "spell_choice"):
            self._cancel_mode()
            return

        if self.mode != "idle":
            self._handle_mode_click(row, col)
            return

        if self.selected_unit_id is not None and (row, col) in self._current_highlights():
            self._handle_idle_unit_click(row, col)
            return

        self._try_select_tile(row, col)

    def _handle_idle_unit_click(self, row, col):
        unit = self.state.units.get(self.selected_unit_id)
        if unit is None:
            return
        action = self._current_highlights().get((row, col))

        if unit.kind == "Ship":
            self._animate_move(unit, row, col, lambda: self.state.move_ship(unit.id, row, col))
            return
        if unit.kind == "CannonBoat":
            if action == "ranged_attack":
                self._animate_ranged_attack(unit, row, col,
                                             lambda: self.state.ranged_attack(unit.id, row, col), "cannonball")
            else:
                self._animate_move(unit, row, col, lambda: self.state.move_cannon_boat(unit.id, row, col))
            return
        if action == "ranged_attack":
            proj = "arrow" if unit.kind == "Archer" else "cannonball"
            self._animate_ranged_attack(unit, row, col,
                                         lambda: self.state.ranged_attack(unit.id, row, col), proj)
            return

        if action == "move":
            self._animate_move(unit, row, col, lambda: self.state.interact(unit.id, row, col))
            return
        if action == "attack":
            self._animate_melee_attack(unit, row, col, lambda: self.state.interact(unit.id, row, col))
            return
        if action == "steal":
            self.state.interact(unit.id, row, col)
            self._clear_selection()
            self._after_state_change()
            return

        # enter_resource / board_ship / barracks / magic_school — без анімації руху,
        # можуть повернути *_choice, який відкриває вибір у нижній панелі.
        outcome = self.state.interact(unit.id, row, col)
        if outcome.get("result") in ("barracks_choice", "magic_school_choice"):
            self.mode = outcome["result"]
            self.mode_context = {"worker_id": outcome["worker_id"], "anchor_pos": (row, col)}
            self._render_map()
            self._refresh_bottom_bar()
            return
        self._clear_selection()
        self._after_state_change()

    def _handle_mode_click(self, row, col):
        ctx = self.mode_context
        outcome = {"result": "blocked"}

        if self.mode == "hire_spawn":
            outcome = self.state.hire_worker(ctx["building_id"], row, col)
        elif self.mode == "withdraw_worker":
            outcome = self.state.withdraw_worker(ctx["building_id"], row, col)
        elif self.mode == "repair_target":
            targets = self.state.get_repairable_targets(ctx["worker_id"])
            b_id = self.state.building_pos.get((row, col))
            u_id = self.state.unit_pos.get((row, col))
            if b_id is not None and ("building", b_id) in targets:
                outcome = self.state.repair_target(ctx["worker_id"], "building", b_id)
            elif u_id is not None and ("unit", u_id) in targets:
                outcome = self.state.repair_target(ctx["worker_id"], "unit", u_id)
            self.mode, self.mode_context = "idle", {}
            self._clear_selection()
            self._after_state_change()
            return
        elif self.mode == "build_tile":
            outcome = self.state.build_building(ctx["worker_id"], ctx["kind"], row, col)
            self.mode, self.mode_context = "idle", {}
            self._clear_selection()
            self._animate_pulse(row, col)
            self._after_state_change()
            return
        elif self.mode == "ship_spawn":
            outcome = self.state.spawn_ship(ctx["port_id"], row, col)
        elif self.mode == "cannon_boat_spawn":
            outcome = self.state.spawn_cannon_boat(ctx["port_id"], row, col)
        elif self.mode == "catapult_spawn":
            outcome = self.state.spawn_catapult(ctx["smithy_id"], row, col)
        elif self.mode == "disembark":
            outcome = self.state.disembark(ctx["ship_id"], ctx["passenger_id"], row, col)
        elif self.mode == "ranged_target":
            unit = self.state.units.get(ctx["unit_id"])
            if unit is not None and (row, col) in self.state.get_ranged_attack_tiles(unit.id):
                proj = "arrow" if unit.kind == "Archer" else "cannonball"
                self._animate_ranged_attack(unit, row, col,
                                             lambda: self.state.ranged_attack(unit.id, row, col), proj)
                self.mode, self.mode_context = "idle", {}
                return
        elif self.mode == "cannon_boat_move":
            unit = self.state.units.get(ctx["boat_id"])
            highlights = self._current_highlights()
            if unit is not None and highlights.get((row, col)) == "ranged_attack":
                self._animate_ranged_attack(unit, row, col,
                                             lambda: self.state.ranged_attack(unit.id, row, col), "cannonball")
            elif unit is not None:
                self._animate_move(unit, row, col, lambda: self.state.move_cannon_boat(unit.id, row, col))
            self.mode, self.mode_context = "idle", {}
            return
        elif self.mode == "spell_target":
            mage_id, spell_name = ctx["mage_id"], ctx["spell_name"]
            if spell_name == "Teleport":
                self.mode = "spell_teleport_destination"
                self.mode_context = {"mage_id": mage_id, "spell_name": spell_name,
                                      "unit_row": row, "unit_col": col}
                self._render_map()
                self._refresh_bottom_bar()
                return
            mage = self.state.units.get(mage_id)
            if mage is not None:
                self._animate_spell(mage, row, col, lambda: self.state.cast_spell(mage_id, spell_name, row, col))
            self.mode, self.mode_context = "idle", {}
            return
        elif self.mode == "spell_teleport_destination":
            mage_id, spell_name = ctx["mage_id"], ctx["spell_name"]
            unit_row, unit_col = ctx["unit_row"], ctx["unit_col"]
            self.state.cast_spell(mage_id, spell_name, unit_row, unit_col, teleport_to=(row, col))
            self.mode, self.mode_context = "idle", {}
            self._clear_selection()
            self._after_state_change()
            return

        self.mode = "idle"
        self.mode_context = {}
        self._clear_selection()
        self._after_state_change()

    def _try_select_tile(self, row, col):
        current_id = self.state.current_player_id
        unit_id = self.state.unit_pos.get((row, col))
        building_id = self.state.building_pos.get((row, col))

        new_unit_id = None
        if unit_id is not None and self.state.units[unit_id].owner_id == current_id:
            new_unit_id = unit_id

        new_building_id = None
        if building_id is not None:
            b = self.state.buildings[building_id]
            if b.owner_id == current_id and b.kind in SELECTABLE_BUILDING_KINDS:
                new_building_id = building_id

        self.selected_unit_id = new_unit_id
        self.selected_building_id = new_building_id

        self._render_map()
        self._refresh_bottom_bar()

    def _clear_selection(self):
        self.selected_unit_id = None
        self.selected_building_id = None

    def _cancel_mode(self):
        self.mode = "idle"
        self.mode_context = {}
        self._render_map()
        self._refresh_bottom_bar()

    def _after_state_change(self):
        if self.state.game_over:
            self._show_victory_screen()
            return
        self._refresh_top_bar()
        self._render_map()
        self._refresh_bottom_bar()
        self.focus_set()

    # ------------------------------------------------------------------
    # Анімації — стан вже змінено (game_logic синхронний), тому кожна
    # анімація лише "наздоганяє" візуально перед фінальним _after_state_change().
    # ------------------------------------------------------------------
    def _run_tween(self, steps, duration_ms, frame_fn, done_fn):
        if self._anim_job is not None:
            try:
                self.after_cancel(self._anim_job)
            except (ValueError, tk.TclError):
                pass
            self._anim_job = None
        dt = max(15, duration_ms // steps)

        def step(i):
            frame_fn((i + 1) / steps)
            if i + 1 < steps:
                self._anim_job = self.after(dt, lambda: step(i + 1))
            else:
                self._anim_job = None
                done_fn()

        step(0)

    def _animate_move(self, unit, to_row, to_col, apply_fn):
        from_row, from_col = unit.row, unit.col
        kind, warrior_type, owner_id = unit.kind, unit.warrior_type, unit.owner_id
        apply_fn()
        self._clear_selection()

        def frame(t):
            self._render_map()
            r = from_row + (to_row - from_row) * t
            c = from_col + (to_col - from_col) * t
            x1, y1, x2, y2 = self._tile_rect(r, c)
            self._draw_unit_at(self.canvas, _GhostUnit(kind, warrior_type, owner_id), x1, y1, x2, y2)

        self._run_tween(7, 170, frame, self._after_state_change)

    def _animate_melee_attack(self, attacker, to_row, to_col, apply_fn):
        from_row, from_col = attacker.row, attacker.col
        kind, warrior_type, owner_id = attacker.kind, attacker.warrior_type, attacker.owner_id
        apply_fn()
        self._clear_selection()

        def frame(t):
            self._render_map()
            lunge = math.sin(t * math.pi) * 0.35
            r = from_row + (to_row - from_row) * lunge
            c = from_col + (to_col - from_col) * lunge
            x1, y1, x2, y2 = self._tile_rect(r, c)
            self._draw_unit_at(self.canvas, _GhostUnit(kind, warrior_type, owner_id), x1, y1, x2, y2)
            if t > 0.4:
                dx1, dy1, dx2, dy2 = self._tile_rect(to_row, to_col)
                self.canvas.create_rectangle(dx1, dy1, dx2, dy2, fill="#e74c3c", stipple="gray50", outline="")

        self._run_tween(8, 220, frame, self._after_state_change)

    def _animate_ranged_attack(self, attacker, to_row, to_col, apply_fn, projectile):
        from_row, from_col = attacker.row, attacker.col
        color_hex = config.PLAYER_COLORS.get(self.state.players[attacker.owner_id].color, "#fff")
        apply_fn()
        self._clear_selection()

        def frame(t):
            self._render_map()
            r = from_row + (to_row - from_row) * t
            c = from_col + (to_col - from_col) * t
            x1, y1, x2, y2 = self._tile_rect(r, c)
            x, y = (x1 + x2) / 2, (y1 + y2) / 2
            size = self.tile_size
            if projectile == "arrow":
                angle = math.atan2(to_row - from_row, to_col - from_col)
                graphics.draw_projectile_arrow(self.canvas, x, y, angle, size * 0.5)
            else:
                graphics.draw_projectile_cannonball(self.canvas, x, y, size * 0.6)
            if t > 0.85:
                dx1, dy1, dx2, dy2 = self._tile_rect(to_row, to_col)
                self.canvas.create_rectangle(dx1, dy1, dx2, dy2, fill="#e74c3c", stipple="gray50", outline="")

        self._run_tween(8, 220, frame, self._after_state_change)

    def _animate_spell(self, mage, to_row, to_col, apply_fn):
        from_row, from_col = mage.row, mage.col
        color_hex = config.PLAYER_COLORS.get(self.state.players[mage.owner_id].color, "#fff")
        apply_fn()
        self._clear_selection()

        def frame(t):
            self._render_map()
            r = from_row + (to_row - from_row) * t
            c = from_col + (to_col - from_col) * t
            x1, y1, x2, y2 = self._tile_rect(r, c)
            graphics.draw_projectile_magic_sparkle(self.canvas, (x1 + x2) / 2, (y1 + y2) / 2,
                                                     self.tile_size * 0.7, color_hex)

        self._run_tween(8, 220, frame, self._after_state_change)

    def _animate_pulse(self, row, col, apply_fn=None):
        if apply_fn is not None:
            apply_fn()

        def frame(t):
            self._render_map()
            x1, y1, x2, y2 = self._tile_rect(row, col)
            inset = self.tile_size * 0.06 * math.sin(t * math.pi * 3)
            self.canvas.create_rectangle(x1 - inset, y1 - inset, x2 + inset, y2 + inset,
                                          outline="#f1c40f", width=3)

        self._run_tween(6, 260, frame, lambda: None)

    # ------------------------------------------------------------------
    # Клавіатура
    # ------------------------------------------------------------------
    def _on_key_press(self, event):
        if event.keysym in ("Left", "Right", "Up", "Down"):
            self._camera_keys_held.add(event.keysym)
            return
        if self.state.current_player().is_bot or self.state.game_over:
            return

        if event.keysym == "Return":
            self._on_end_turn_clicked()
            return
        if event.keysym == "Escape":
            if self.mode != "idle":
                self._cancel_mode()
            else:
                self._on_exit_clicked()
            return

        char = event.char.lower() if event.char else ""

        if self.mode == "barracks_choice":
            unit_type = config.KEY_TO_BARRACKS_UNIT.get(char)
            if unit_type:
                self._on_promote_chosen(self.mode_context["worker_id"], unit_type)
            return
        if self.mode == "tower_upgrade_choice":
            for kind, key in config.TOWER_UPGRADE_HOTKEYS.items():
                if char == key:
                    self._on_tower_upgrade_chosen(self.mode_context["tower_id"], kind)
                    return
            return
        if self.mode == "spell_choice":
            for name, data in config.SPELLS.items():
                if char == data["shortcut"]:
                    self._on_spell_chosen(self.mode_context["mage_id"], name)
                    return
            return
        if self.mode == "magic_school_choice":
            if char == "m":
                self._on_hire_mage_chosen(self.mode_context["worker_id"])
            return

        if self.mode != "idle":
            return

        unit = self.state.units.get(self.selected_unit_id) if self.selected_unit_id is not None else None
        building = self.state.buildings.get(self.selected_building_id) \
            if self.selected_building_id is not None else None

        if char == "w" and building is not None and building.kind in ("Castle", "House"):
            self._start_hire_mode(); return

        if building is not None and building.kind == "Smithy":
            for tech, key in config.SMITHY_TECH_HOTKEYS.items():
                if char == key and tech in self.state.get_available_techs(building.id):
                    self._on_start_research(building.id, tech); return

        if char in "123456" and building is not None and building.kind == "Port":
            idx = int(char) - 1
            if 0 <= idx < len(config.PORT_TRADE_PAIRS):
                give, get = config.PORT_TRADE_PAIRS[idx]
                self._on_trade(building.id, give, get); return

        if char == "v" and building is not None and building.kind == "Port":
            self._start_ship_spawn_mode(); return

        if char == "c" and unit is not None and unit.kind == "Mage" and not self.state._is_exhausted(unit):
            self._start_spell_choice(); return

        if char == "z" and building is not None and self.state.can_demolish(building.id):
            self._on_demolish_clicked(building.id); return

        if char in ("q", "w", "e") and unit is not None and unit.kind == "Ship" and unit.passengers:
            idx = {"q": 0, "w": 1, "e": 2}[char]
            if idx < len(unit.passengers):
                self._start_disembark_mode(unit.passengers[idx]); return

        if char == "q" and isinstance(building, ResourceBuilding) and building.workers_inside:
            self._start_withdraw_mode(); return

        if char == "g" and unit is not None:
            if self.state.get_standing_enterable_building(unit.id) is not None:
                self._on_go_inside_clicked(unit.id); return

        if unit is not None and unit.kind == "Worker" and not self.state._is_exhausted(unit):
            if char == "r":
                self._start_repair_mode(); return
            build_kind = config.KEY_TO_BUILD_KIND.get(char)
            if build_kind is not None:
                self._start_build_mode(build_kind); return

    def _on_key_release(self, event):
        self._camera_keys_held.discard(event.keysym)

    # ------------------------------------------------------------------
    # Info-strip (замінює спливаючий тултіп — ціна показується іконками)
    # ------------------------------------------------------------------
    def _set_hover_info(self, label, cost=None, ap=None, extra=None):
        self.info_label.configure(text=label)
        for w in self.info_icons_frame.winfo_children():
            w.destroy()
        icon_funcs = {"gold": graphics.draw_icon_gold, "wood": graphics.draw_icon_wood, "food": graphics.draw_icon_food}
        if cost:
            for res in ("gold", "wood", "food"):
                amt = cost.get(res, 0)
                if amt:
                    graphics.render_icon(self.info_icons_frame, icon_funcs[res], size=20, bg=INFO_STRIP_BG).pack(side="left")
                    tk.Label(self.info_icons_frame, text=str(amt), fg="white", bg=INFO_STRIP_BG,
                             font=("Arial", 10, "bold")).pack(side="left", padx=(0, 8))
        if ap is not None:
            tk.Label(self.info_icons_frame, text=f"{ap} AP", fg="#74b9ff", bg=INFO_STRIP_BG,
                     font=("Arial", 10, "bold")).pack(side="left", padx=(0, 8))
        if extra:
            tk.Label(self.info_icons_frame, text=extra, fg="#bbbbbb", bg=INFO_STRIP_BG,
                     font=("Arial", 9, "italic")).pack(side="left")

    def _clear_hover_info(self):
        self._set_hover_info("", None, None, None)

    # ------------------------------------------------------------------
    # Нижня панель
    # ------------------------------------------------------------------
    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg=BOTTOM_BAR_BG, height=BOTTOM_BAR_HEIGHT)
        bar.pack(side="bottom", fill="x")
        bar.pack_propagate(False)

        info_strip = tk.Frame(bar, bg=INFO_STRIP_BG, height=INFO_STRIP_HEIGHT)
        info_strip.pack(side="top", fill="x")
        info_strip.pack_propagate(False)
        self.info_label = tk.Label(info_strip, text="", fg="white", bg=INFO_STRIP_BG, font=("Arial", 11, "bold"))
        self.info_label.pack(side="left", padx=10)
        self.info_icons_frame = tk.Frame(info_strip, bg=INFO_STRIP_BG)
        self.info_icons_frame.pack(side="left", padx=6)

        self.action_frame = tk.Frame(bar, bg=BOTTOM_BAR_BG)
        self.action_frame.pack(fill="both", expand=True, padx=14, pady=8)

    def _refresh_bottom_bar(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        self._clear_hover_info()

        current = self.state.current_player()

        if current.is_bot:
            tk.Label(self.action_frame, text="Bot is playing...", fg="white", bg=BOTTOM_BAR_BG,
                     font=("Arial", 16, "italic")).pack(expand=True)
            self.after(1200, self._bot_end_turn)
            return

        if self.mode == "barracks_choice":
            self._build_barracks_choice(current); return
        if self.mode == "magic_school_choice":
            self._build_magic_school_choice(current); return
        if self.mode == "tower_upgrade_choice":
            self._build_tower_upgrade_choice(current); return
        if self.mode == "spell_choice":
            self._build_spell_choice(current); return

        if self.mode != "idle":
            tk.Label(self.action_frame, text="Choose a highlighted tile on the map...",
                     fg="white", bg=BOTTOM_BAR_BG, font=("Arial", 13, "italic")).pack(side="left", padx=10)
            RoundedButton(self.action_frame, text="Cancel", command=self._cancel_mode,
                          width=130, height=48, bg="#7f8c8d", hover_bg="#95a5a6",
                          font=("Arial", 12, "bold")).pack(side="right", padx=10)
            return

        has_unit = self.selected_unit_id is not None
        has_building = self.selected_building_id is not None

        if has_unit:
            self._build_unit_actions(current)
        if has_unit and has_building:
            tk.Frame(self.action_frame, bg="#3a5a7a", width=2).pack(side="left", fill="y", padx=8, pady=4)
        if has_building:
            self._build_building_actions(current)

        RoundedButton(
            self.action_frame, text="End Turn (Enter)", command=self._on_end_turn_clicked,
            width=170, height=56, bg="#27ae60", hover_bg="#2ecc71", font=("Arial", 13, "bold"),
        ).pack(side="right", padx=10)

    # ------------------------------------------------------------------
    # Слот кнопки дії — іконка + підпис + (не)доступність + hover-info
    # ------------------------------------------------------------------
    def _make_action_slot(self, parent, draw_func, label, command=None, *, cost=None, ap=None,
                           extra=None, enabled=True, grid_pos=None, **draw_kwargs):
        slot = tk.Frame(parent, bg=SLOT_BG, width=76, height=76,
                         highlightbackground="#2c4c6b", highlightthickness=1)
        slot.pack_propagate(False)
        if grid_pos is not None:
            r, c = grid_pos
            slot.grid(row=r, column=c, padx=4, pady=4)
        else:
            slot.pack(side="left", padx=6)

        widgets = [slot]
        if draw_func is not None:
            icon = graphics.render_icon(slot, draw_func, size=38, bg=SLOT_BG, **draw_kwargs)
            icon.pack(pady=(6, 1))
            widgets.append(icon)
            if not enabled:
                block = tk.Canvas(icon, width=38, height=38, bg=SLOT_BG, highlightthickness=0)
                block.place(x=0, y=0)
                graphics.draw_block_icon(block, 1, 1, 37, 37)

        text = tk.Label(slot, text=label, fg=("white" if enabled else "#7f8c8d"), bg=SLOT_BG,
                         font=("Arial", 8, "bold"), wraplength=70)
        text.pack(pady=(1 if draw_func is None else 0, 0))
        widgets.append(text)

        if enabled and command is not None:
            for widget in widgets:
                widget.bind("<Button-1>", lambda e: command())
                widget.bind("<Enter>", lambda e: slot.configure(highlightbackground="#5dade2"), add="+")
                widget.bind("<Leave>", lambda e: slot.configure(highlightbackground="#2c4c6b"), add="+")

        for widget in widgets:
            widget.bind("<Enter>", lambda e: self._set_hover_info(label, cost, ap, extra), add="+")
            widget.bind("<Leave>", lambda e: self._clear_hover_info(), add="+")

        return slot

    # ------------------------------------------------------------------
    # Іконки технологій/заклинань — Кузня повторно використовує спрайт
    # прокачаного юніта (ТЗ), заклинання — свою власну іконку.
    # ------------------------------------------------------------------
    def _spell_icon_func(self, spell_name, color_hex):
        mapping = {
            "Heal": lambda c, x1, y1, x2, y2: graphics.draw_icon_heal(c, x1, y1, x2, y2, color_hex),
            "Freeze": lambda c, x1, y1, x2, y2: graphics.draw_icon_freeze(c, x1, y1, x2, y2),
            "MagicShield": lambda c, x1, y1, x2, y2: graphics.draw_icon_magic_shield(c, x1, y1, x2, y2, color_hex),
            "SummonSlime": lambda c, x1, y1, x2, y2: graphics.draw_icon_summon_slime(c, x1, y1, x2, y2, color_hex),
            "YouShallNotPass": lambda c, x1, y1, x2, y2: graphics.draw_icon_bridge_gone(c, x1, y1, x2, y2, color_hex),
            "Thunder": lambda c, x1, y1, x2, y2: graphics.draw_icon_thunder(c, x1, y1, x2, y2, color_hex),
            "Teleport": lambda c, x1, y1, x2, y2: graphics.draw_icon_teleport(c, x1, y1, x2, y2, color_hex),
        }
        return mapping.get(spell_name, mapping["Heal"])

    def _tech_icon_func(self, tech_name, color_hex):
        if tech_name == "Bread":
            return lambda c, x1, y1, x2, y2: graphics.draw_icon_bread(c, x1, y1, x2, y2)
        if tech_name == "Horses":
            return lambda c, x1, y1, x2, y2: graphics.draw_icon_horse(c, x1, y1, x2, y2, color_hex)
        if tech_name == "Bow":
            return lambda c, x1, y1, x2, y2: graphics.draw_archer(c, x1, y1, x2, y2, color_hex, action_points=2)
        if tech_name == "Crossbow":
            return lambda c, x1, y1, x2, y2: graphics.draw_archer(c, x1, y1, x2, y2, color_hex,
                                                                    action_points=2, crossbow=True)
        if tech_name == "BetterRepair":
            return graphics.draw_hammer_icon
        if tech_name == "ArmoredTowers":
            return lambda c, x1, y1, x2, y2: graphics.draw_icon_armored_towers(c, x1, y1, x2, y2, color_hex)
        if tech_name == "Shields":
            return lambda c, x1, y1, x2, y2: graphics.draw_warrior(c, x1, y1, x2, y2, color_hex, "Sword",
                                                                     action_points=2, shield=True)
        if tech_name == "BetterMaces":
            return lambda c, x1, y1, x2, y2: graphics.draw_warrior(c, x1, y1, x2, y2, color_hex, "Mace",
                                                                     action_points=2, better_mace=True)
        if tech_name == "Alebards":
            return lambda c, x1, y1, x2, y2: graphics.draw_warrior(c, x1, y1, x2, y2, color_hex, "Spear",
                                                                     action_points=2, alebard=True)
        if tech_name == "HeavyArtillery":
            return graphics.draw_icon_heavy_artillery
        if tech_name == "FasterHorses":
            return lambda c, x1, y1, x2, y2: graphics.draw_horseman(c, x1, y1, x2, y2, color_hex,
                                                                       action_points=4, has_faster_horses=True)
        if tech_name in config.SPELLS:
            return self._spell_icon_func(tech_name, color_hex)
        return graphics.draw_hammer_icon

    def _upgrade_icon_func(self, color_hex):
        def draw(canvas, x1, y1, x2, y2):
            w, h = x2 - x1, y2 - y1
            cx = x1 + w / 2
            canvas.create_polygon(cx, y1 + h * 0.1, x1 + w * 0.2, y1 + h * 0.55, x1 + w * 0.38, y1 + h * 0.55,
                                   x1 + w * 0.38, y2 - h * 0.1, x2 - w * 0.38, y2 - h * 0.1,
                                   x2 - w * 0.38, y1 + h * 0.55, x2 - w * 0.2, y1 + h * 0.55,
                                   fill=color_hex, outline="black", width=2)
        return draw

    # ------------------------------------------------------------------
    # Дії обраної будівлі
    # ------------------------------------------------------------------
    def _build_building_actions(self, current):
        b = self.state.buildings.get(self.selected_building_id)
        if b is None or b.owner_id != current.id:
            return
        color_hex = config.PLAYER_COLORS.get(current.color)
        group = tk.Frame(self.action_frame, bg=BOTTOM_BAR_BG)
        group.pack(side="left")

        if b.kind in ("Castle", "House"):
            can = (current.can_afford(config.WORKER_HIRE_COST)
                   and self.state.house_used(current.id) < self.state.house_limit(current.id))
            self._make_action_slot(group, graphics.draw_worker, "Hire Worker (W)",
                                    self._start_hire_mode if can else None,
                                    cost=config.WORKER_HIRE_COST, enabled=can,
                                    color_hex=color_hex, action_points=2)
        elif isinstance(b, ResourceBuilding):
            self._build_resource_building_actions(group, current, b, color_hex)
        elif b.kind == "Barracks":
            tk.Label(group, text="Send a Worker next to this Barracks to train units.",
                     fg="#bbbbbb", bg=BOTTOM_BAR_BG, font=("Arial", 10, "italic")).pack(side="left", padx=10)
        elif b.kind == "Smithy":
            self._build_smithy_actions(group, current, b, color_hex)
        elif b.kind == "HorseStable":
            self._build_tech_slots(group, current, b, color_hex)
        elif b.kind == "MagicSchool":
            self._build_tech_slots(group, current, b, color_hex)
        elif isinstance(b, Tower):
            self._build_tower_actions(group, current, b, color_hex)
        elif b.kind == "Port":
            self._build_port_actions(group, current, b, color_hex)

        if self.state.can_demolish(b.id):
            refund = self.state.get_demolish_refund(b.id)
            self._make_action_slot(group, graphics.draw_demolish_icon, "Demolish (Z)",
                                    lambda bid=b.id: self._on_demolish_clicked(bid),
                                    cost=refund, extra="refund")

    def _build_tech_slots(self, group, current, b, color_hex):
        if b.researching_tech is not None:
            icon_fn = self._tech_icon_func(b.researching_tech, color_hex)
            self._make_action_slot(group, icon_fn, f"Researching\n{b.researching_tech}",
                                    lambda: self._on_cancel_research(b.id),
                                    extra="click to cancel (full refund)")
            return
        for tech_name, cost in self.state.get_available_techs(b.id).items():
            can = current.can_afford(cost)
            icon_fn = self._tech_icon_func(tech_name, color_hex)
            self._make_action_slot(group, icon_fn, tech_name,
                                    (lambda t=tech_name: self._on_start_research(b.id, t)) if can else None,
                                    cost=cost, enabled=can)

    def _build_resource_building_actions(self, group, current, b, color_hex):
        if b.workers_inside:
            self._make_action_slot(group, graphics.draw_worker, "Withdraw (Q)",
                                    self._start_withdraw_mode, extra="free",
                                    color_hex=color_hex, action_points=0)
        if not b.upgraded:
            if b.upgrading:
                pct = f"{b.upgrade_progress}/{config.BUILDING_UPGRADE_TARGET_PROGRESS}"
                self._make_action_slot(group, self._upgrade_icon_func(color_hex), f"Upgrading {pct}",
                                        lambda: self._on_cancel_upgrade(b.id),
                                        extra="click to cancel (refund 1 each)")
            else:
                cost = config.BUILDING_UPGRADE_COST[b.kind]
                can = bool(b.workers_inside) and current.can_afford(cost)
                self._make_action_slot(group, self._upgrade_icon_func(color_hex), "Upgrade",
                                        (lambda: self._on_start_upgrade(b.id)) if can else None,
                                        cost=cost, enabled=can,
                                        extra=None if b.workers_inside else "needs a worker inside")
        self._build_tech_slots(group, current, b, color_hex)

    def _build_smithy_actions(self, group, current, b, color_hex):
        self._build_tech_slots(group, current, b, color_hex)
        if current.has_tech("HeavyArtillery"):
            can = current.can_afford(config.CATAPULT_COST)
            self._make_action_slot(group, graphics.draw_catapult, "Build Catapult",
                                    (lambda: self._start_catapult_spawn_mode(b.id)) if can else None,
                                    cost=config.CATAPULT_COST, enabled=can)

    def _build_tower_actions(self, group, current, b, color_hex):
        if b.tower_type is None and b.upgrading_to is None:
            options = self.state.get_tower_upgrade_options(b.id)
            icon_fn = lambda c, x1, y1, x2, y2: graphics.draw_tower(c, x1, y1, x2, y2, color_hex)
            enabled = bool(options)
            self._make_action_slot(group, icon_fn, "Upgrade Tower",
                                    self._start_tower_upgrade_choice if enabled else None,
                                    enabled=enabled,
                                    extra=None if enabled else "research a tower tech first")
        elif b.upgrading_to is not None:
            tk.Label(group, text=f"Becoming {b.upgrading_to} next turn...", fg="white", bg=BOTTOM_BAR_BG,
                     font=("Arial", 11, "italic")).pack(side="left", padx=10)
        else:
            tk.Label(group, text=f"{b.tower_type} — fires automatically each turn", fg="white",
                     bg=BOTTOM_BAR_BG, font=("Arial", 11, "italic")).pack(side="left", padx=10)

    def _build_port_actions(self, group, current, b, color_hex):
        icon_funcs = {"gold": graphics.draw_icon_gold, "wood": graphics.draw_icon_wood, "food": graphics.draw_icon_food}
        for idx, (give, get) in enumerate(config.PORT_TRADE_PAIRS):
            can = current.resources.get(give, 0) >= config.PORT_TRADE_GIVE_AMOUNT
            self._make_action_slot(
                group, icon_funcs[give], f"{give[0].upper()}->{get[0].upper()} ({idx + 1})",
                (lambda g=give, t=get: self._on_trade(b.id, g, t)) if can else None,
                cost={give: config.PORT_TRADE_GIVE_AMOUNT}, enabled=can,
                extra=f"-> +{config.PORT_TRADE_GET_AMOUNT} {get}",
            )
        can_ship = current.can_afford(config.SHIP_COST)
        self._make_action_slot(group, graphics.draw_ship, "Build Ship (V)",
                                self._start_ship_spawn_mode if can_ship else None,
                                cost=config.SHIP_COST, enabled=can_ship, color_hex=color_hex)
        if current.has_tech("HeavyArtillery"):
            can_cb = current.can_afford(config.CANNON_BOAT_COST)
            self._make_action_slot(group, graphics.draw_cannon_boat, "Build Cannon Boat",
                                    self._start_cannon_boat_spawn_mode if can_cb else None,
                                    cost=config.CANNON_BOAT_COST, enabled=can_cb, color_hex=color_hex)

    # ------------------------------------------------------------------
    # Дії обраного юніта
    # ------------------------------------------------------------------
    def _build_unit_actions(self, current):
        u = self.state.units.get(self.selected_unit_id)
        if u is None or u.owner_id != current.id:
            return
        color_hex = config.PLAYER_COLORS.get(current.color)
        group = tk.Frame(self.action_frame, bg=BOTTOM_BAR_BG)
        group.pack(side="left")

        enter_target = self.state.get_standing_enterable_building(u.id)
        if enter_target is not None:
            self._make_action_slot(group, graphics.draw_enter_icon, "Go Inside (G)",
                                    lambda: self._on_go_inside_clicked(u.id),
                                    extra="free (0 AP)", color_hex=color_hex)

        if self.state._is_exhausted(u):
            tk.Label(group, text="No action points left", fg="white", bg=BOTTOM_BAR_BG,
                     font=("Arial", 12, "italic")).pack(side="left", padx=10)
            return

        if u.kind == "Worker":
            self._build_worker_actions(group, current, u)
        elif u.kind == "Mage":
            self._make_action_slot(group, graphics.draw_mage, "Cast Spell (C)",
                                    self._start_spell_choice, color_hex=color_hex, action_points=u.action_points)
        elif u.kind == "Ship" and u.passengers:
            hotkeys = ["Q", "W", "E"]
            for i, passenger_id in enumerate(list(u.passengers)):
                passenger = self.state.units[passenger_id]
                self._make_action_slot(
                    group, lambda c, x1, y1, x2, y2, p=passenger: self._draw_unit_at(c, p, x1, y1, x2, y2),
                    f"Disembark ({hotkeys[i] if i < 3 else '?'})",
                    lambda pid=passenger_id: self._start_disembark_mode(pid), extra="free",
                )

    def _build_worker_actions(self, group, current, worker):
        color_hex = config.PLAYER_COLORS.get(current.color)
        icons_area = tk.Frame(group, bg=BOTTOM_BAR_BG)
        icons_area.pack(side="left", fill="y")

        repair_targets = self.state.get_repairable_targets(worker.id)
        repair_enabled = bool(repair_targets) and current.can_afford(config.WORKER_REPAIR_COST)
        repair_amount = (config.WORKER_REPAIR_AMOUNT_UPGRADED if current.has_tech("BetterRepair")
                          else config.WORKER_REPAIR_AMOUNT)
        slots = [(
            "Repair (R)", graphics.draw_hammer_icon, {},
            self._start_repair_mode if repair_enabled else None,
            config.WORKER_REPAIR_COST, config.ACTION_COST_REPAIR, f"+{repair_amount} HP", repair_enabled,
        )]
        for kind in config.BUILDABLE_KINDS:
            draw_func = self._make_building_icon_func(kind, color_hex)
            cost = config.BUILDING_COSTS[kind]
            locked = kind == "HorseStable" and not current.has_tech(config.HORSE_STABLE_REQUIRES_TECH)
            can = current.can_afford(cost) and not locked
            slots.append((
                BUILDING_LABELS[kind], draw_func, {}, self._make_build_starter(kind) if can else None,
                cost, config.ACTION_COST_BUILD, ("needs Horses tech" if locked else None), can,
            ))

        for i, (label, draw_func, draw_kwargs, command, cost, ap, extra, enabled) in enumerate(slots):
            row, col = divmod(i, 6)
            self._make_action_slot(icons_area, draw_func, label, command, cost=cost, ap=ap, extra=extra,
                                    enabled=enabled, grid_pos=(row, col), **draw_kwargs)

    @staticmethod
    def _make_building_icon_func(kind, color_hex):
        def draw(canvas, x1, y1, x2, y2):
            graphics.draw_building(canvas, x1, y1, x2, y2, kind, color_hex)
        return draw

    def _make_build_starter(self, kind):
        return lambda: self._start_build_mode(kind)

    # ------------------------------------------------------------------
    # Вибір у нижній панелі (Barracks / Magic School / Tower upgrade / Spell)
    # ------------------------------------------------------------------
    def _build_barracks_choice(self, current):
        color_hex = config.PLAYER_COLORS.get(current.color)
        worker_id = self.mode_context["worker_id"]
        tk.Label(self.action_frame, text="Train a unit:", fg="white", bg=BOTTOM_BAR_BG,
                 font=("Arial", 13, "bold")).pack(side="left", padx=(4, 14))

        options = [
            ("Sword", config.WARRIOR_COSTS["Sword"],
             lambda c, x1, y1, x2, y2: graphics.draw_warrior(c, x1, y1, x2, y2, color_hex, "Sword", action_points=2)),
            ("Spear", config.WARRIOR_COSTS["Spear"],
             lambda c, x1, y1, x2, y2: graphics.draw_warrior(c, x1, y1, x2, y2, color_hex, "Spear", action_points=2)),
            ("Mace", config.WARRIOR_COSTS["Mace"],
             lambda c, x1, y1, x2, y2: graphics.draw_warrior(c, x1, y1, x2, y2, color_hex, "Mace", action_points=2)),
            ("Archer", config.ARCHER_COST,
             lambda c, x1, y1, x2, y2: graphics.draw_archer(c, x1, y1, x2, y2, color_hex, action_points=2)),
            ("Horseman", config.HORSEMAN_COST,
             lambda c, x1, y1, x2, y2: graphics.draw_horseman(c, x1, y1, x2, y2, color_hex, action_points=3)),
        ]
        for name, cost, icon_fn in options:
            extra = None
            can = current.can_afford(cost)
            if name == "Horseman":
                if self.state.horse_used(current.id) >= self.state.horse_limit(current.id):
                    can = False
                    extra = "needs a free Horse slot"
            self._make_action_slot(
                self.action_frame, icon_fn, f"{name} ({BARRACKS_UNIT_HOTKEY.get(name, '')})",
                (lambda n=name: self._on_promote_chosen(worker_id, n)) if can else None,
                cost=cost, enabled=can, extra=extra,
            )
        RoundedButton(self.action_frame, text="Cancel", command=self._cancel_mode,
                      width=130, height=48, bg="#7f8c8d", hover_bg="#95a5a6",
                      font=("Arial", 12, "bold")).pack(side="right", padx=10)

    def _build_magic_school_choice(self, current):
        color_hex = config.PLAYER_COLORS.get(current.color)
        worker_id = self.mode_context["worker_id"]
        can = current.can_afford(config.MAGE_HIRE_COST)
        tk.Label(self.action_frame, text="Train at the Magic School:", fg="white", bg=BOTTOM_BAR_BG,
                 font=("Arial", 13, "bold")).pack(side="left", padx=(4, 14))
        self._make_action_slot(self.action_frame, graphics.draw_mage, "Mage (M)",
                                (lambda: self._on_hire_mage_chosen(worker_id)) if can else None,
                                cost=config.MAGE_HIRE_COST, enabled=can, color_hex=color_hex, action_points=2)
        RoundedButton(self.action_frame, text="Cancel", command=self._cancel_mode,
                      width=130, height=48, bg="#7f8c8d", hover_bg="#95a5a6",
                      font=("Arial", 12, "bold")).pack(side="right", padx=10)

    def _build_tower_upgrade_choice(self, current):
        color_hex = config.PLAYER_COLORS.get(current.color)
        tower_id = self.mode_context["tower_id"]
        options = self.state.get_tower_upgrade_options(tower_id)
        tk.Label(self.action_frame, text="Upgrade tower to:", fg="white", bg=BOTTOM_BAR_BG,
                 font=("Arial", 13, "bold")).pack(side="left", padx=(4, 14))
        for kind in options:
            cost = config.TOWER_UPGRADE_COST[kind]
            can = current.can_afford(cost)
            icon_fn = lambda c, x1, y1, x2, y2, k=kind: graphics.draw_tower(c, x1, y1, x2, y2, color_hex, tower_type=k)
            self._make_action_slot(
                self.action_frame, icon_fn, f"{kind} ({TOWER_UPGRADE_HOTKEY.get(kind, '')})",
                (lambda k=kind: self._on_tower_upgrade_chosen(tower_id, k)) if can else None,
                cost=cost, enabled=can,
            )
        RoundedButton(self.action_frame, text="Cancel", command=self._cancel_mode,
                      width=130, height=48, bg="#7f8c8d", hover_bg="#95a5a6",
                      font=("Arial", 12, "bold")).pack(side="right", padx=10)

    def _build_spell_choice(self, current):
        color_hex = config.PLAYER_COLORS.get(current.color)
        mage_id = self.mode_context["mage_id"]
        tk.Label(self.action_frame, text="Cast a spell:", fg="white", bg=BOTTOM_BAR_BG,
                 font=("Arial", 13, "bold")).pack(side="left", padx=(4, 10))
        for name, data in config.SPELLS.items():
            if data["tech_cost"] is not None and not current.has_tech(name):
                continue
            can = current.can_afford(data["use_cost"])
            icon_fn = self._spell_icon_func(name, color_hex)
            self._make_action_slot(
                self.action_frame, icon_fn, f"{name} ({data['shortcut'].upper()})",
                (lambda n=name: self._on_spell_chosen(mage_id, n)) if can else None,
                cost=data["use_cost"], enabled=can, extra=f"range {data['range']}",
            )
        RoundedButton(self.action_frame, text="Cancel", command=self._cancel_mode,
                      width=130, height=48, bg="#7f8c8d", hover_bg="#95a5a6",
                      font=("Arial", 12, "bold")).pack(side="right", padx=10)

    # ------------------------------------------------------------------
    # Запуск режимів вибору клітинки
    # ------------------------------------------------------------------
    def _start_hire_mode(self):
        self.mode, self.mode_context = "hire_spawn", {"building_id": self.selected_building_id}
        self._render_map(); self._refresh_bottom_bar()

    def _start_withdraw_mode(self):
        self.mode, self.mode_context = "withdraw_worker", {"building_id": self.selected_building_id}
        self._render_map(); self._refresh_bottom_bar()

    def _start_ship_spawn_mode(self):
        self.mode, self.mode_context = "ship_spawn", {"port_id": self.selected_building_id}
        self._render_map(); self._refresh_bottom_bar()

    def _start_cannon_boat_spawn_mode(self):
        self.mode, self.mode_context = "cannon_boat_spawn", {"port_id": self.selected_building_id}
        self._render_map(); self._refresh_bottom_bar()

    def _start_catapult_spawn_mode(self, smithy_id):
        self.mode, self.mode_context = "catapult_spawn", {"smithy_id": smithy_id}
        self._render_map(); self._refresh_bottom_bar()

    def _start_repair_mode(self):
        self.mode, self.mode_context = "repair_target", {"worker_id": self.selected_unit_id}
        self._render_map(); self._refresh_bottom_bar()

    def _start_build_mode(self, kind):
        self.mode = "build_tile"
        self.mode_context = {"worker_id": self.selected_unit_id, "kind": kind}
        self._render_map(); self._refresh_bottom_bar()

    def _start_disembark_mode(self, passenger_id):
        self.mode = "disembark"
        self.mode_context = {"ship_id": self.selected_unit_id, "passenger_id": passenger_id}
        self._render_map(); self._refresh_bottom_bar()

    def _start_tower_upgrade_choice(self):
        self.mode = "tower_upgrade_choice"
        self.mode_context = {"tower_id": self.selected_building_id,
                              "anchor_pos": self._selected_position()}
        self._render_map(); self._refresh_bottom_bar()

    def _start_spell_choice(self):
        self.mode = "spell_choice"
        self.mode_context = {"mage_id": self.selected_unit_id, "anchor_pos": self._selected_position()}
        self._render_map(); self._refresh_bottom_bar()

    def _on_go_inside_clicked(self, unit_id):
        self.state.enter_building_free(unit_id)
        self._clear_selection()
        self._after_state_change()

    def _on_promote_chosen(self, worker_id, unit_type):
        outcome = self.state.promote_worker(worker_id, unit_type)
        self.mode, self.mode_context = "idle", {}
        self._clear_selection()
        self._after_state_change()
        if outcome.get("result") != "promoted":
            messagebox.showinfo("Little Kingdoms", "Not enough resources (or no free Horse slot).")

    def _on_hire_mage_chosen(self, worker_id):
        outcome = self.state.hire_mage(worker_id)
        self.mode, self.mode_context = "idle", {}
        self._clear_selection()
        self._after_state_change()
        if outcome.get("result") != "promoted":
            messagebox.showinfo("Little Kingdoms", "Not enough resources to hire a mage.")

    def _on_tower_upgrade_chosen(self, tower_id, upgrade_kind):
        self.state.start_tower_upgrade(tower_id, upgrade_kind)
        self.mode, self.mode_context = "idle", {}
        self._clear_selection()
        self._after_state_change()

    def _on_spell_chosen(self, mage_id, spell_name):
        self.mode = "spell_target"
        self.mode_context = {"mage_id": mage_id, "spell_name": spell_name}
        self._render_map(); self._refresh_bottom_bar()

    def _on_start_upgrade(self, building_id):
        self.state.start_building_upgrade(building_id)
        self._animate_pulse(*self._entity_pos(building_id, is_building=True))
        self._after_state_change()

    def _on_cancel_upgrade(self, building_id):
        self.state.cancel_building_upgrade(building_id)
        self._after_state_change()

    def _on_start_research(self, building_id, tech_name):
        self.state.start_research(building_id, tech_name)
        self._after_state_change()

    def _on_cancel_research(self, building_id):
        self.state.cancel_research(building_id)
        self._after_state_change()

    def _on_trade(self, port_id, give, get):
        self.state.trade_at_port(port_id, give, get)
        self._after_state_change()

    def _entity_pos(self, entity_id, is_building):
        entity = self.state.buildings[entity_id] if is_building else self.state.units[entity_id]
        return entity.row, entity.col

    def _on_demolish_clicked(self, building_id):
        refund = self.state.get_demolish_refund(building_id)
        confirmed = messagebox.askyesno(
            "Demolish building",
            f"Are you sure you want to demolish this building?\nRefund: {_format_cost(refund)}",
        )
        if confirmed:
            self.state.demolish_building(building_id)
            self._clear_selection()
            self._after_state_change()

    # ------------------------------------------------------------------
    # Чат (Local зараз; шлях відправки готовий під LAN)
    # ------------------------------------------------------------------
    def _build_chat_panel(self):
        self.chat_panel = tk.Frame(self._canvas_container, bg="#0e1c2c", width=260)
        self.chat_panel.pack_propagate(False)

        history_frame = tk.Frame(self.chat_panel, bg="#0e1c2c")
        history_frame.pack(side="top", fill="both", expand=True, padx=8, pady=(8, 4))
        self.chat_text = tk.Text(history_frame, bg="#16324f", fg="white", font=("Arial", 10),
                                  state="disabled", wrap="word", relief="flat")
        self.chat_text.pack(side="left", fill="both", expand=True)
        scroll = tk.Scrollbar(history_frame, command=self.chat_text.yview)
        scroll.pack(side="right", fill="y")
        self.chat_text.configure(yscrollcommand=scroll.set)

        entry_row = tk.Frame(self.chat_panel, bg="#0e1c2c")
        entry_row.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        self.chat_entry = tk.Entry(entry_row, font=("Arial", 10))
        self.chat_entry.pack(side="left", fill="x", expand=True)
        self.chat_entry.bind("<Return>", lambda e: self._on_chat_send())
        RoundedButton(entry_row, text="Send", command=self._on_chat_send,
                      width=60, height=30, bg="#27ae60", hover_bg="#2ecc71", font=("Arial", 9, "bold"),
                      ).pack(side="left", padx=(6, 0))

    def _toggle_chat(self):
        self.chat_visible = not self.chat_visible
        if self.chat_visible:
            self.chat_panel.pack(side="right", fill="y")
        else:
            self.chat_panel.pack_forget()
        self.after(10, self._recompute_layout_and_render)

    def _on_chat_send(self):
        text = self.chat_entry.get().strip()
        if not text:
            return
        self.chat_entry.delete(0, "end")
        self._send_chat_message(self.state.current_player_id, text)

    def _send_chat_message(self, player_id, text):
        """Єдина точка входу для чату. Зараз просто дописує в локальний
        журнал — коли з'явиться LAN, мережевий шар викликатиме цей самий
        метод для повідомлень, що прийшли від інших гравців, і не
        доведеться переписувати цей файл."""
        color = self.state.players[player_id].color
        self.chat_log.append((color, text))
        self._refresh_chat_display()

    def _refresh_chat_display(self):
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", "end")
        for color, text in self.chat_log[-200:]:
            self.chat_text.insert("end", f"{color}: {text}\n")
        self.chat_text.configure(state="disabled")
        self.chat_text.see("end")

    # ------------------------------------------------------------------
    # Кінець ходу
    # ------------------------------------------------------------------
    def _on_end_turn_clicked(self):
        self.state.end_turn()
        self._clear_selection()
        self.mode, self.mode_context = "idle", {}
        self._after_state_change()
        self._follow_camera_to_current_castle()

    def _bot_end_turn(self):
        self.state.end_turn()
        self._clear_selection()
        self.mode, self.mode_context = "idle", {}
        self._after_state_change()
        self._follow_camera_to_current_castle()

    # ------------------------------------------------------------------
    # Плавне центрування камери на замку гравця при зміні ходу
    # ------------------------------------------------------------------
    def _follow_camera_to_current_castle(self):
        if self.zoom <= 0.0:
            return
        current = self.state.current_player()
        castle = next(
            (b for b in self.state.buildings.values() if b.owner_id == current.id and b.kind == "Castle"),
            None,
        )
        if castle is None:
            return
        visible_cols, visible_rows = self._visible_span()
        max_col = max(0.0, self.grid_cols - visible_cols)
        max_row = max(0.0, self.grid_rows - visible_rows)
        target_col = min(max(0.0, castle.col - visible_cols / 2 + 0.5), max_col)
        target_row = min(max(0.0, castle.row - visible_rows / 2 + 0.5), max_row)
        self._animate_camera_to(target_row, target_col)

    def _animate_camera_to(self, target_row, target_col, steps=12):
        if self._camera_anim_job is not None:
            self.after_cancel(self._camera_anim_job)
            self._camera_anim_job = None
        self._camera_anim_step(self.cam_row, self.cam_col, target_row, target_col, 0, steps)

    def _camera_anim_step(self, start_row, start_col, target_row, target_col, step, steps):
        t = (step + 1) / steps
        t = 1 - (1 - t) ** 2
        self.cam_row = start_row + (target_row - start_row) * t
        self.cam_col = start_col + (target_col - start_col) * t
        self._clamp_camera()
        self._render_map()
        if step + 1 < steps:
            self._camera_anim_job = self.after(
                20, self._camera_anim_step, start_row, start_col, target_row, target_col, step + 1, steps
            )
        else:
            self._camera_anim_job = None

    # ------------------------------------------------------------------
    # Перемога
    # ------------------------------------------------------------------
    def _show_victory_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

        winner = self.state.players.get(self.state.winner_id) if self.state.winner_id is not None else None
        color_hex = config.PLAYER_COLORS.get(winner.color, "#ffffff") if winner else "#ffffff"
        text = f"Player {winner.color} wins!" if winner else "Draw - all players were eliminated."

        tk.Label(self, text=text, fg=color_hex, bg=CANVAS_BG, font=("Arial", 32, "bold")).place(
            relx=0.5, rely=0.42, anchor="center")
        RoundedButton(
            self, text="Main Menu", command=lambda: self.app.show_screen(MenuScreen),
            width=220, height=60, bg="#27ae60", hover_bg="#2ecc71", font=("Arial", 15, "bold"),
        ).place(relx=0.5, rely=0.55, anchor="center")

    # ------------------------------------------------------------------
    # Вихід у головне меню
    # ------------------------------------------------------------------
    def _on_exit_clicked(self):
        confirmed = messagebox.askyesno(
            "Exit to menu",
            "Are you sure you want to exit to the main menu?\nCurrent game progress will be lost.",
        )
        if confirmed:
            self.app.show_screen(MenuScreen)


class _GhostUnit:
    """Легка структура-заглушка для анімаційних кадрів: несе рівно ті
    поля, які потребує GameScreen._draw_unit_at, без прив'язки до живого
    запису в GameState (юніт міг уже загинути/змінити позицію до кінця
    анімації)."""

    def __init__(self, kind, warrior_type, owner_id):
        self.kind = kind
        self.warrior_type = warrior_type
        self.owner_id = owner_id
        self.action_points = 2
        self.tired = False
