"""
Little Kingdoms — векторний рендеринг (Beta).

Усі функції малюють безпосередньо на переданому tkinter.Canvas у межах
прямокутника (x1, y1, x2, y2). Це дозволяє використовувати ОДНІ й ТІ Ж
функції як для великих тайлів/юнітів на ігровій карті, так і для
маленьких іконок на кнопках дій — просто передаючи менший прямокутник.
render_icon() унизу — стандартний спосіб зробити таку кнопку-іконку.

Команда-колір (color_hex): усюди, де намальовано щось "командного
кольору" (дах будівлі, тіло юніта, прапор), використовується
PLAYER_COLORS-значення власника. Нейтральні деталі (дерево, камінь,
вогонь кузні, метал) — завжди фіксовані кольори, не командні.

Технології, що змінюють вигляд воїна (Shields/BetterMaces/Alebards),
НЕ зберігаються тут — graphics.py лише вміє намалювати кожен варіант;
який саме варіант показати (тобто чи є в гравця відповідна технологія)
вирішує ui_game.py, що має доступ до GameState.

ВІДОМІ СПРОЩЕННЯ / TODO:
  - Орієнтація мосту (горизонтальний/вертикальний/хрест) залежить від
    сусідніх тайлів на сітці, а ця функція сітки не бачить — тому
    draw_bridge() приймає готовий параметр orientation; яку саме
    orientation обчислити для конкретної клітинки, вирішує ui_game.py.
  - Анімація (кадри ходьби/атаки/снаряди в польоті) — це відповідальність
    ui_game.py (планувальник кадрів); тут лише статичні пози/спрайти
    (для Farm — параметр frame 0/1, для Slime/Horseman — параметр
    action_points, що й так по суті "кадр" відповідно до логіки гри).
"""

import math
import tkinter as tk

from world_gen import TILE_GRASS, TILE_FOREST, TILE_WHEAT, TILE_MOUNTAIN, TILE_WATER


# ---------------------------------------------------------------------------
# Кольори тайлів
# ---------------------------------------------------------------------------

COLOR_GRASS_BG = "#00cc00"
COLOR_GRASS_OUTLINE = "#00a300"

COLOR_FOREST_BG = "#0b5e0b"
COLOR_FOREST_OUTLINE = "#083d08"
COLOR_TREE = "#00cc00"
COLOR_TRUNK = "#6b3f1d"

COLOR_WHEAT_BG = "#ffee00"
COLOR_WHEAT_OUTLINE = "#e6d600"

COLOR_MOUNTAIN_BG = "#9e9e9e"
COLOR_MOUNTAIN_OUTLINE = "#7a7a7a"
COLOR_MOUNTAIN_PEAK = "#6e6e6e"
COLOR_SNOW = "#ffffff"

COLOR_WATER_BG = "#0080ff"
COLOR_WATER_OUTLINE = "#0066cc"
COLOR_WAVE = "#ffffff"

COLOR_HP_BG = "#7f1d1d"
COLOR_HP_FG = "#2ecc71"

COLOR_WOOD = "#8d5524"
COLOR_WOOD_DARK = "#5c3a1a"
COLOR_STONE = "#9e9e9e"
COLOR_STONE_DARK = "#7a7a7a"
COLOR_METAL = "#7f8c8d"
COLOR_METAL_LIGHT = "#dfe6e9"
COLOR_GOLD_YELLOW = "#f1c40f"
COLOR_FIRE = "#e67e22"


# ---------------------------------------------------------------------------
# Тайли (без змін відносно Alpha)
# ---------------------------------------------------------------------------

def draw_grass(canvas, x1, y1, x2, y2):
    canvas.create_rectangle(x1, y1, x2, y2, fill=COLOR_GRASS_BG, outline=COLOR_GRASS_OUTLINE)


def draw_forest(canvas, x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    canvas.create_rectangle(x1, y1, x2, y2, fill=COLOR_FOREST_BG, outline=COLOR_FOREST_OUTLINE)

    cx = x1 + w / 2
    canvas.create_rectangle(
        cx - w * 0.07, y1 + h * 0.72, cx + w * 0.07, y2 - h * 0.06,
        fill=COLOR_TRUNK, outline="black",
    )
    canvas.create_polygon(
        cx - w * 0.32, y1 + h * 0.78,
        cx + w * 0.32, y1 + h * 0.78,
        cx, y1 + h * 0.32,
        fill=COLOR_TREE, outline="black",
    )
    canvas.create_polygon(
        cx - w * 0.22, y1 + h * 0.5,
        cx + w * 0.22, y1 + h * 0.5,
        cx, y1 + h * 0.1,
        fill=COLOR_TREE, outline="black",
    )


def draw_wheat(canvas, x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    canvas.create_rectangle(x1, y1, x2, y2, fill=COLOR_WHEAT_BG, outline=COLOR_WHEAT_OUTLINE)

    cx = x1 + w / 2
    line_kwargs = dict(fill="black", width=max(1, int(w * 0.04)))

    top_wide_l, top_wide_r = cx - w * 0.32, cx + w * 0.32
    top_narrow_l, top_narrow_r = cx - w * 0.14, cx + w * 0.14
    top_y0, top_y1 = y1 + h * 0.12, y1 + h * 0.3
    canvas.create_line(top_wide_l, top_y0, top_wide_r, top_y0, **line_kwargs)
    canvas.create_line(top_wide_l, top_y0, top_narrow_l, top_y1, **line_kwargs)
    canvas.create_line(top_wide_r, top_y0, top_narrow_r, top_y1, **line_kwargs)
    canvas.create_line(top_narrow_l, top_y1, top_narrow_r, top_y1, **line_kwargs)

    mid_wide_l, mid_wide_r = cx - w * 0.24, cx + w * 0.24
    mid_narrow_l, mid_narrow_r = cx - w * 0.08, cx + w * 0.08
    mid_y0, mid_y1 = y1 + h * 0.36, y1 + h * 0.52
    canvas.create_line(mid_wide_l, mid_y0, mid_wide_r, mid_y0, **line_kwargs)
    canvas.create_line(mid_wide_l, mid_y0, mid_narrow_l, mid_y1, **line_kwargs)
    canvas.create_line(mid_wide_r, mid_y0, mid_narrow_r, mid_y1, **line_kwargs)
    canvas.create_line(mid_narrow_l, mid_y1, mid_narrow_r, mid_y1, **line_kwargs)

    stem_l, stem_r = cx - w * 0.06, cx + w * 0.06
    stem_y1 = y2 - h * 0.1
    canvas.create_rectangle(stem_l, mid_y1, stem_r, stem_y1, outline="black")


def draw_mountain(canvas, x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    canvas.create_rectangle(x1, y1, x2, y2, fill=COLOR_MOUNTAIN_BG, outline=COLOR_MOUNTAIN_OUTLINE)

    cx = x1 + w / 2
    canvas.create_polygon(
        cx, y1 + h * 0.08,
        x1 + w * 0.14, y2 - h * 0.08,
        x2 - w * 0.14, y2 - h * 0.08,
        fill=COLOR_MOUNTAIN_PEAK, outline="black",
    )
    canvas.create_polygon(
        cx, y1 + h * 0.08,
        cx - w * 0.13, y1 + h * 0.32,
        cx + w * 0.13, y1 + h * 0.32,
        fill=COLOR_SNOW, outline="black",
    )


def draw_water(canvas, x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    canvas.create_rectangle(x1, y1, x2, y2, fill=COLOR_WATER_BG, outline=COLOR_WATER_OUTLINE)

    wave_width = max(2, int(w * 0.05))
    for wy in (y1 + h * 0.38, y1 + h * 0.72):
        canvas.create_line(
            x1 + w * 0.12, wy,
            x1 + w * 0.31, wy - h * 0.08,
            x1 + w * 0.5, wy,
            x1 + w * 0.69, wy + h * 0.08,
            x1 + w * 0.88, wy,
            fill=COLOR_WAVE, width=wave_width, smooth=True,
        )


_TILE_DRAW_FUNCS = {
    TILE_GRASS: draw_grass,
    TILE_FOREST: draw_forest,
    TILE_WHEAT: draw_wheat,
    TILE_MOUNTAIN: draw_mountain,
    TILE_WATER: draw_water,
}


def draw_tile(canvas, x1, y1, x2, y2, tile_type):
    """Малює тайл потрібного типу. Клітинка завжди повертає свій
    первісний вигляд, якщо на ній немає юніта чи будівлі — цю функцію
    достатньо викликати кожен раз заново при перемальовуванні."""
    draw_func = _TILE_DRAW_FUNCS.get(tile_type, draw_grass)
    draw_func(canvas, x1, y1, x2, y2)


# ---------------------------------------------------------------------------
# Допоміжне: симетричні зубці (Castle і Tower використовують те саме)
# ---------------------------------------------------------------------------

def _draw_symmetric_merlons(canvas, x1, x2, top_y, bottom_y, color_hex, count=3):
    """count зубців порівну розподілені по ширині з РІВНИМИ проміжками з
    обох боків (gap-merlon-gap-merlon-...-gap), а не притиснуті до краю."""
    w = x2 - x1
    unit = w / (count * 2 + 1)
    for i in range(count):
        mx1 = x1 + unit * (1 + 2 * i)
        mx2 = mx1 + unit
        canvas.create_rectangle(mx1, top_y, mx2, bottom_y, fill=color_hex, outline="black")


# ---------------------------------------------------------------------------
# Замок
# ---------------------------------------------------------------------------

def draw_castle(canvas, x1, y1, x2, y2, color_hex):
    """Малює вежу замку, зафарбовану кольором команди-власника. Зубці —
    рівні й симетричні (виправлено відносно Alpha)."""
    w, h = x2 - x1, y2 - y1

    body_x1, body_y1 = x1 + w * 0.18, y1 + h * 0.38
    body_x2, body_y2 = x2 - w * 0.18, y2 - h * 0.08
    canvas.create_rectangle(body_x1, body_y1, body_x2, body_y2, fill=color_hex, outline="black", width=2)

    _draw_symmetric_merlons(canvas, body_x1, body_x2, body_y1 - h * 0.12, body_y1, color_hex, count=3)

    door_w = (body_x2 - body_x1) * 0.28
    cx = (body_x1 + body_x2) / 2
    canvas.create_rectangle(cx - door_w / 2, body_y2 - h * 0.22, cx + door_w / 2, body_y2,
                             fill="#3b2412", outline="black")

    canvas.create_line(cx, body_y1 - h * 0.12, cx, y1 + h * 0.02, fill="#3b2412", width=2)
    canvas.create_polygon(cx, y1 + h * 0.02, cx + w * 0.16, y1 + h * 0.08, cx, y1 + h * 0.14,
                           fill=COLOR_GOLD_YELLOW, outline="black")


# ---------------------------------------------------------------------------
# Юніти — базова постать (робітник) і енергія через руки
# ---------------------------------------------------------------------------

def draw_worker(canvas, x1, y1, x2, y2, color_hex, action_points=2):
    """Малює робітника. action_points: 2 = обидві руки вгору (повний запас),
    1 = одна рука вгору одна вниз (частково втомлений),
    0 (або менше) = обидві руки вниз (повністю втомлений, дій не лишилось).
    Це саме "правило рук" використовують і Warrior, і Archer, і Mage."""
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2

    canvas.create_oval(cx - w * 0.16, y1 + h * 0.12, cx + w * 0.16, y1 + h * 0.4,
                        fill=color_hex, outline="black", width=2)
    canvas.create_line(cx, y1 + h * 0.4, cx, y1 + h * 0.68, fill="black", width=2)

    left_up = action_points >= 2
    right_up = action_points >= 1
    if left_up:
        canvas.create_line(cx - w * 0.24, y1 + h * 0.3, cx, y1 + h * 0.48, fill="black", width=2)
    else:
        canvas.create_line(cx - w * 0.22, y1 + h * 0.58, cx, y1 + h * 0.48, fill="black", width=2)
    if right_up:
        canvas.create_line(cx + w * 0.24, y1 + h * 0.3, cx, y1 + h * 0.48, fill="black", width=2)
    else:
        canvas.create_line(cx + w * 0.22, y1 + h * 0.58, cx, y1 + h * 0.48, fill="black", width=2)

    canvas.create_line(cx, y1 + h * 0.68, cx - w * 0.18, y2 - h * 0.06, fill="black", width=2)
    canvas.create_line(cx, y1 + h * 0.68, cx + w * 0.18, y2 - h * 0.06, fill="black", width=2)


def draw_enter_icon(canvas, x1, y1, x2, y2, color_hex="#f1c40f"):
    w, h = x2 - x1, y2 - y1
    cx, cy = x1 + w / 2, y1 + h / 2
    inner = min(w, h) * 0.16
    outer = min(w, h) * 0.42
    lw = max(2, int(w * 0.07))

    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x_out, y_out = cx + dx * outer, cy + dy * outer
        x_in, y_in = cx + dx * inner, cy + dy * inner
        canvas.create_line(x_out, y_out, x_in, y_in, fill=color_hex, width=lw, arrow="last",
                            arrowshape=(8, 10, 4))


def draw_hammer_icon(canvas, x1, y1, x2, y2):
    """Молоток — і кнопка ремонту, і іконка технології 'Better Repair'."""
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    canvas.create_rectangle(cx - w * 0.06, y1 + h * 0.3, cx + w * 0.06, y2 - h * 0.1,
                             fill=COLOR_WOOD, outline="black")
    canvas.create_rectangle(cx - w * 0.3, y1 + h * 0.12, cx + w * 0.3, y1 + h * 0.34,
                             fill=COLOR_METAL, outline="black", width=2)


# ---------------------------------------------------------------------------
# Смужка здоровʼя / бейджі
# ---------------------------------------------------------------------------

def draw_hp_bar(canvas, x1, y1, x2, y2, hp, max_hp):
    if max_hp <= 0 or hp >= max_hp:
        return
    w = x2 - x1
    bar_y0 = y2 - (y2 - y1) * 0.09
    bar_y1 = y2 - (y2 - y1) * 0.03
    bar_x0 = x1 + w * 0.12
    bar_x1 = x2 - w * 0.12
    canvas.create_rectangle(bar_x0, bar_y0, bar_x1, bar_y1, fill=COLOR_HP_BG, outline="")
    ratio = max(0.0, hp / max_hp)
    fg_x1 = bar_x0 + (bar_x1 - bar_x0) * ratio
    canvas.create_rectangle(bar_x0, bar_y0, fg_x1, bar_y1, fill=COLOR_HP_FG, outline="")


def draw_count_badge(canvas, x1, y1, x2, y2, count, max_count=None):
    if count <= 0:
        return
    w = x2 - x1
    r = w * 0.16
    bx, by = x2 - r * 1.2, y1 + r * 1.2
    canvas.create_oval(bx - r, by - r, bx + r, by + r, fill="#1c1c1c", outline="white")
    text = f"{count}/{max_count}" if max_count else str(count)
    canvas.create_text(bx, by, text=text, fill="white", font=("Arial", max(7, int(r * 0.9)), "bold"))


def draw_demolish_icon(canvas, x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    cx, cy = x1 + w / 2, y1 + h / 2
    r = min(w, h) * 0.38
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#c0392b", outline="black", width=2)
    lw = max(2, int(w * 0.09))
    canvas.create_line(cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5, fill="white", width=lw)
    canvas.create_line(cx - r * 0.5, cy + r * 0.5, cx + r * 0.5, cy - r * 0.5, fill="white", width=lw)


def draw_block_icon(canvas, x1, y1, x2, y2):
    """Червоне перекреслене коло — накладається на кнопку недоступної дії
    (не вистачає ресурсів/технології/AP тощо)."""
    w, h = x2 - x1, y2 - y1
    cx, cy = x1 + w / 2, y1 + h / 2
    r = min(w, h) * 0.46
    lw = max(2, int(min(w, h) * 0.09))
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#e74c3c", width=lw)
    canvas.create_line(cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7, fill="#e74c3c", width=lw)


def render_icon(master, draw_func, size=44, bg=None, padding=4, **draw_kwargs):
    """Створює маленький Canvas і малює на ньому draw_func у зменшеному
    масштабі. Використовується для іконок на кнопках дій (той самий
    векторний рендер, що й на карті, лише менших розмірів)."""
    bg = bg or master["bg"]
    icon = tk.Canvas(master, width=size, height=size, bg=bg, highlightthickness=0)
    draw_func(icon, padding, padding, size - padding, size - padding, **draw_kwargs)
    return icon


# ---------------------------------------------------------------------------
# Будівлі
# ---------------------------------------------------------------------------

def draw_house(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    body_y0 = y1 + h * 0.5
    canvas.create_rectangle(x1 + w * 0.2, body_y0, x2 - w * 0.2, y2 - h * 0.08,
                             fill=color_hex, outline="black", width=2)
    canvas.create_polygon(cx, y1 + h * 0.18, x1 + w * 0.12, body_y0, x2 - w * 0.12, body_y0,
                           fill=COLOR_WOOD, outline="black", width=2)
    canvas.create_rectangle(cx - w * 0.08, y2 - h * 0.3, cx + w * 0.08, y2 - h * 0.08,
                             fill="#3b2412", outline="black")


def _draw_horse_head(canvas, cx, cy, size, color_hex, eye="dot"):
    """Спільна голова коня (профіль вправо, з шиєю) — використовується і
    для Horse Barn/іконки ресурсу Horse (завжди командного кольору), і
    для Horseman. eye: "dot" (кінь не спить) / "none" (3є очко вже
    витрачене, але кінь ще не спить) / "dash" (кінь спить, 0 AP)."""
    s = size
    canvas.create_polygon(
        cx - s * 0.22, cy + s * 0.55,          # шия, низ-ліво
        cx - s * 0.32, cy + s * 0.05,          # шия, вигин назад
        cx - s * 0.18, cy - s * 0.3,           # потилиця
        cx - s * 0.26, cy - s * 0.48,          # кінчик вуха
        cx - s * 0.06, cy - s * 0.32,          # основа вуха
        cx + s * 0.04, cy - s * 0.46,          # чоло
        cx + s * 0.3, cy - s * 0.3,            # перенісся
        cx + s * 0.4, cy - s * 0.04,           # морда (перед)
        cx + s * 0.3, cy + s * 0.12,           # морда (низ)
        cx + s * 0.12, cy + s * 0.04,          # підборіддя
        cx + s * 0.1, cy + s * 0.55,           # шия, низ-право
        fill=color_hex, outline="black", width=2, smooth=True,
    )
    ex, ey = cx + s * 0.02, cy - s * 0.16
    if eye == "dot":
        canvas.create_oval(ex - s * 0.05, ey - s * 0.05, ex + s * 0.05, ey + s * 0.05,
                            fill="black", outline="")
    elif eye == "dash":
        canvas.create_line(ex - s * 0.07, ey, ex + s * 0.07, ey, fill="black", width=2)
    # eye == "none" -> нічого не малюємо


def draw_horse_stable(canvas, x1, y1, x2, y2, color_hex):
    """Horse Barn — той самий силует, що й House, але замість дверей
    кінська голова (Стайня дає ресурс Horse — та сама іконографіка)."""
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    body_y0 = y1 + h * 0.5
    canvas.create_rectangle(x1 + w * 0.14, body_y0, x2 - w * 0.14, y2 - h * 0.06,
                             fill=COLOR_WOOD, outline="black", width=2)
    canvas.create_polygon(cx, y1 + h * 0.16, x1 + w * 0.06, body_y0, x2 - w * 0.06, body_y0,
                           fill=color_hex, outline="black", width=2)
    _draw_horse_head(canvas, cx, y1 + h * 0.72, w * 0.55, color_hex, eye="dot")


def draw_smithy(canvas, x1, y1, x2, y2, color_hex):
    """Кузня: сірий димар + брунатне тіло + дах командного кольору +
    помаранчевий вогонь (вогонь НІКОЛИ не командного кольору)."""
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2

    canvas.create_rectangle(cx + w * 0.14, y1 + h * 0.06, cx + w * 0.3, y1 + h * 0.58,
                             fill=COLOR_STONE, outline="black", width=2)
    canvas.create_rectangle(x1 + w * 0.1, y1 + h * 0.32, x2 - w * 0.1, y1 + h * 0.5,
                             fill=color_hex, outline="black", width=2)
    canvas.create_rectangle(x1 + w * 0.16, y1 + h * 0.5, x2 - w * 0.16, y2 - h * 0.06,
                             fill=COLOR_WOOD, outline="black", width=2)
    canvas.create_rectangle(cx - w * 0.14, y1 + h * 0.58, cx + w * 0.1, y2 - h * 0.06,
                             fill=COLOR_METAL, outline="black", width=1)
    canvas.create_rectangle(cx - w * 0.08, y1 + h * 0.66, cx + w * 0.04, y2 - h * 0.1,
                             fill=COLOR_FIRE, outline="black")


def draw_magic_school(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    canvas.create_rectangle(x1 + w * 0.08, y1 + h * 0.42, x1 + w * 0.34, y2 - h * 0.06,
                             fill=COLOR_STONE, outline="black", width=2)
    canvas.create_rectangle(x2 - w * 0.34, y1 + h * 0.42, x2 - w * 0.08, y2 - h * 0.06,
                             fill=COLOR_STONE, outline="black", width=2)
    canvas.create_rectangle(cx - w * 0.2, y1 + h * 0.3, cx + w * 0.2, y2 - h * 0.06,
                             fill=COLOR_STONE, outline="black", width=2)
    canvas.create_arc(cx - w * 0.2, y1 + h * 0.02, cx + w * 0.2, y1 + h * 0.58,
                       start=0, extent=180, fill=color_hex, outline="black", width=2, style="chord")
    canvas.create_oval(cx - w * 0.08, y1 + h * 0.42, cx + w * 0.08, y1 + h * 0.58,
                        fill=color_hex, outline="black")
    canvas.create_polygon(cx - w * 0.08, y2 - h * 0.06, cx - w * 0.08, y1 + h * 0.72,
                           cx, y1 + h * 0.62, cx + w * 0.08, y1 + h * 0.72, cx + w * 0.08, y2 - h * 0.06,
                           fill="#3b2412", outline="black")


def draw_lumbermill(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    canvas.create_rectangle(x1 + w * 0.05, y1 + h * 0.05, x2 - w * 0.05, y2 - h * 0.05,
                             fill=COLOR_WOOD, outline="black", width=2)
    canvas.create_rectangle(x1 + w * 0.12, y1 + h * 0.55, x2 - w * 0.12, y2 - h * 0.1,
                             fill=color_hex, outline="black")
    cx, cy = x1 + w * 0.5, y1 + h * 0.32
    canvas.create_oval(cx - w * 0.16, cy - w * 0.16, cx + w * 0.16, cy + w * 0.16,
                        fill=COLOR_METAL_LIGHT, outline="black", width=2)
    for i in range(8):
        angle = i * (math.pi / 4)
        canvas.create_line(cx, cy, cx + math.cos(angle) * w * 0.18, cy + math.sin(angle) * w * 0.18,
                            fill="black", width=1)


def draw_farm(canvas, x1, y1, x2, y2, color_hex, frame=0):
    """Вітряк-Ферма. 2 кадри анімації — лопаті повернуті на пів-кроку
    (кадр перемикає ui_game.py по таймеру, поки будівля щось виробляє)."""
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    canvas.create_rectangle(cx - w * 0.14, y1 + h * 0.3, cx + w * 0.14, y2 - h * 0.08,
                             fill=color_hex, outline="black", width=2)
    canvas.create_polygon(cx, y1 + h * 0.08, cx - w * 0.16, y1 + h * 0.3, cx + w * 0.16, y1 + h * 0.3,
                           fill=COLOR_METAL_LIGHT, outline="black")
    cy = y1 + h * 0.16
    offset = (math.pi / 4) if frame else 0.0
    for i in range(4):
        angle = offset + i * (math.pi / 2)
        canvas.create_line(cx, cy, cx + math.cos(angle) * w * 0.22, cy + math.sin(angle) * w * 0.22,
                            fill=COLOR_GOLD_YELLOW, width=max(3, int(w * 0.07)))
    canvas.create_oval(cx - w * 0.03, cy - w * 0.03, cx + w * 0.03, cy + w * 0.03,
                        fill="black", outline="")


def draw_mine(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    canvas.create_rectangle(x1 + w * 0.05, y1 + h * 0.05, x2 - w * 0.05, y2 - h * 0.05,
                             fill=COLOR_STONE, outline="black", width=2)
    canvas.create_polygon(cx - w * 0.22, y2 - h * 0.1, cx - w * 0.22, y1 + h * 0.35,
                           cx, y1 + h * 0.2, cx + w * 0.22, y1 + h * 0.35, cx + w * 0.22, y2 - h * 0.1,
                           fill=color_hex, outline="black", width=2)
    canvas.create_oval(cx - w * 0.12, y1 + h * 0.42, cx + w * 0.12, y2 - h * 0.1,
                        fill="#1c1c1c", outline="black")


def draw_barracks(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    canvas.create_rectangle(x1 + w * 0.2, y1 + h * 0.35, x1 + w * 0.28, y2 - h * 0.06,
                             fill=COLOR_WOOD, outline="black")
    canvas.create_rectangle(x2 - w * 0.28, y1 + h * 0.35, x2 - w * 0.2, y2 - h * 0.06,
                             fill=COLOR_WOOD, outline="black")
    canvas.create_polygon(x1 + w * 0.08, y2 - h * 0.06, cx, y1 + h * 0.1, x2 - w * 0.08, y2 - h * 0.06,
                           fill=color_hex, outline="black", width=2)


def draw_port(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    canvas.create_rectangle(x1 + w * 0.1, y1 + h * 0.55, x2 - w * 0.1, y1 + h * 0.68,
                             fill=COLOR_WOOD, outline="black")
    for fx in (0.25, 0.5, 0.75):
        canvas.create_line(x1 + w * fx, y1 + h * 0.68, x1 + w * fx, y2 - h * 0.05, fill=COLOR_WOOD, width=3)
    canvas.create_line(x1 + w * 0.2, y1 + h * 0.55, x1 + w * 0.2, y1 + h * 0.15, fill="#3b2412", width=2)
    canvas.create_polygon(x1 + w * 0.2, y1 + h * 0.15, x1 + w * 0.5, y1 + h * 0.28, x1 + w * 0.2, y1 + h * 0.32,
                           fill=color_hex, outline="black")


# ---------------------------------------------------------------------------
# Вежа (5.4 rework): база + симетричні зубці + "наконечник" типу +
# заброньована основа (Armored Towers) — один сірий прямокутник знизу.
# ---------------------------------------------------------------------------

def _draw_tower_topper(canvas, cx, top_y, w, tower_type, color_hex):
    if tower_type == "ArcherTower":
        canvas.create_polygon(cx, top_y - w * 0.2, cx - w * 0.08, top_y, cx + w * 0.08, top_y,
                               fill=COLOR_METAL_LIGHT, outline="black")
        canvas.create_rectangle(cx - w * 0.02, top_y, cx + w * 0.02, top_y + w * 0.1,
                                 fill=COLOR_WOOD, outline="")
    elif tower_type == "MageTower":
        canvas.create_oval(cx - w * 0.14, top_y - w * 0.28, cx + w * 0.14, top_y,
                            fill=color_hex, outline="black", width=2)
    elif tower_type == "CannonTower":
        canvas.create_rectangle(cx - w * 0.16, top_y - w * 0.14, cx + w * 0.12, top_y + w * 0.02,
                                 fill=COLOR_STONE, outline="black", width=2)
        canvas.create_rectangle(cx - w * 0.04, top_y - w * 0.24, cx + w * 0.16, top_y - w * 0.04,
                                 fill=COLOR_FIRE, outline="black", width=2)


def draw_tower(canvas, x1, y1, x2, y2, color_hex, tower_type=None, armored=False):
    """tower_type: None (базова, ще нічого не вміє) / "ArcherTower" /
    "MageTower" / "CannonTower". armored: тех. Armored Towers — завжди
    один і той самий сірий прямокутник знизу, незалежно від типу."""
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    body_x1, body_x2 = cx - w * 0.22, cx + w * 0.22
    body_y1, body_y2 = y1 + h * 0.12, y2 - h * 0.06

    canvas.create_rectangle(body_x1, body_y1, body_x2, body_y2, fill=color_hex, outline="black", width=2)
    _draw_symmetric_merlons(canvas, body_x1, body_x2, y1 + h * 0.02, body_y1, color_hex, count=3)

    if tower_type is not None:
        _draw_tower_topper(canvas, cx, y1 + h * 0.02, w, tower_type, color_hex)

    if armored:
        canvas.create_rectangle(body_x1 - w * 0.03, body_y2 - h * 0.16, body_x2 + w * 0.03, body_y2,
                                 fill=COLOR_STONE, outline="black", width=2)


# ---------------------------------------------------------------------------
# Мости — 3 орієнтації (горизонтальний / вертикальний / перехрестя)
# ---------------------------------------------------------------------------

def draw_bridge_horizontal(canvas, x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    canvas.create_rectangle(x1, y1 + h * 0.3, x2, y2 - h * 0.3, fill=COLOR_WOOD, outline="black", width=2)
    for fx in (0.15, 0.4, 0.65, 0.9):
        canvas.create_line(x1 + w * fx, y1 + h * 0.3, x1 + w * fx, y2 - h * 0.3, fill=COLOR_WOOD_DARK, width=2)


def draw_bridge_vertical(canvas, x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    canvas.create_rectangle(x1 + w * 0.3, y1, x2 - w * 0.3, y2, fill=COLOR_WOOD, outline="black", width=2)
    for fy in (0.15, 0.4, 0.65, 0.9):
        canvas.create_line(x1 + w * 0.3, y1 + h * fy, x2 - w * 0.3, y1 + h * fy, fill=COLOR_WOOD_DARK, width=2)


def draw_bridge_cross(canvas, x1, y1, x2, y2):
    """4-сторонній перетин — просто 2 мости накладені один на одного."""
    draw_bridge_horizontal(canvas, x1, y1, x2, y2)
    draw_bridge_vertical(canvas, x1, y1, x2, y2)


_BRIDGE_DRAW_FUNCS = {
    "horizontal": draw_bridge_horizontal,
    "vertical": draw_bridge_vertical,
    "cross": draw_bridge_cross,
}


def draw_bridge(canvas, x1, y1, x2, y2, orientation="horizontal"):
    """orientation обчислюється в ui_game.py на основі сусідніх тайлів
    (яка сторона — вода, яка — суходіл); тут лише готовий рендер."""
    _BRIDGE_DRAW_FUNCS.get(orientation, draw_bridge_horizontal)(canvas, x1, y1, x2, y2)


def draw_under_construction(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    canvas.create_rectangle(x1 + 2, y1 + 2, x2 - 2, y2 - 2, fill="#d9c38a", outline=color_hex, width=3)
    step = w / 4
    x = x1
    while x < x2:
        canvas.create_line(x, y2 - 2, min(x + step, x2), max(y1 + 2, y2 - step), fill=COLOR_WOOD, width=2)
        x += step
    draw_hammer_icon(canvas, x1 + w * 0.28, y1 + h * 0.18, x1 + w * 0.72, y1 + h * 0.62)


BUILDING_DRAW_FUNCS = {
    "Castle": draw_castle,
    "House": draw_house,
    "LumberMill": draw_lumbermill,
    "Mill": draw_farm,
    "Mine": draw_mine,
    "Barracks": draw_barracks,
    "Port": draw_port,
    "Smithy": draw_smithy,
    "HorseStable": draw_horse_stable,
    "MagicSchool": draw_magic_school,
}


def draw_building(canvas, x1, y1, x2, y2, kind, color_hex, tower_type=None, armored=False,
                   bridge_orientation="horizontal", farm_frame=0):
    if kind == "Tower":
        draw_tower(canvas, x1, y1, x2, y2, color_hex, tower_type=tower_type, armored=armored)
    elif kind == "Bridge":
        draw_bridge(canvas, x1, y1, x2, y2, orientation=bridge_orientation)
    elif kind == "UnderConstruction":
        draw_under_construction(canvas, x1, y1, x2, y2, color_hex)
    elif kind == "Mill":
        draw_farm(canvas, x1, y1, x2, y2, color_hex, frame=farm_frame)
    else:
        draw_func = BUILDING_DRAW_FUNCS.get(kind)
        if draw_func:
            draw_func(canvas, x1, y1, x2, y2, color_hex)


# ---------------------------------------------------------------------------
# Воїни: Меч / Булава / Спис + прокачані варіанти (Shields/BetterMaces/Alebards)
# ---------------------------------------------------------------------------

def _draw_sword(canvas, cx, top_y, bottom_y, size, color_hex, shield=False):
    canvas.create_line(cx, top_y, cx, bottom_y, fill=COLOR_METAL_LIGHT, width=max(2, int(size * 0.08)))
    canvas.create_line(cx - size * 0.13, top_y + size * 0.12, cx + size * 0.13, top_y + size * 0.12,
                        fill=color_hex, width=max(2, int(size * 0.05)))
    if shield:
        # На протилежному від меча боці (ближче до лівого краю персонажа),
        # на висоті тулуба — щоб не перекривати голову.
        sx = cx - size * 0.75
        sy = top_y + size * 0.32
        r = size * 0.13
        canvas.create_polygon(
            sx - r, sy - r * 0.4, sx - r * 0.4, sy - r, sx + r * 0.4, sy - r, sx + r, sy - r * 0.4,
            sx + r, sy + r * 0.4, sx + r * 0.4, sy + r, sx - r * 0.4, sy + r, sx - r, sy + r * 0.4,
            fill=color_hex, outline="black", width=2,
        )


def _draw_mace(canvas, cx, top_y, bottom_y, size, color_hex, better=False):
    canvas.create_line(cx, top_y + size * 0.1, cx, bottom_y, fill=COLOR_WOOD, width=max(2, int(size * 0.06)))
    canvas.create_rectangle(cx - size * 0.14, top_y - size * 0.06, cx + size * 0.14, top_y + size * 0.22,
                             fill=COLOR_METAL, outline="black", width=2)
    if better:
        canvas.create_polygon(
            cx, top_y - size * 0.02, cx + size * 0.08, top_y + size * 0.08,
            cx, top_y + size * 0.18, cx - size * 0.08, top_y + size * 0.08,
            fill=color_hex, outline="black",
        )
        canvas.create_oval(cx - size * 0.03, top_y + size * 0.05, cx + size * 0.03, top_y + size * 0.11,
                            fill=color_hex, outline="black")


def _draw_spear(canvas, cx, top_y, bottom_y, size, color_hex, alebard=False):
    canvas.create_line(cx, top_y, cx, bottom_y, fill=COLOR_WOOD, width=max(2, int(size * 0.05)))
    canvas.create_polygon(cx, top_y - size * 0.06, cx - size * 0.08, top_y + size * 0.1,
                           cx + size * 0.08, top_y + size * 0.1, fill=COLOR_METAL_LIGHT, outline="black")
    if alebard:
        canvas.create_polygon(
            cx + size * 0.02, top_y + size * 0.02, cx + size * 0.24, top_y + size * 0.08,
            cx + size * 0.24, top_y + size * 0.16, cx + size * 0.02, top_y + size * 0.14,
            fill=color_hex, outline="black",
        )


def draw_warrior(canvas, x1, y1, x2, y2, color_hex, warrior_type, action_points=2,
                  shield=False, better_mace=False, alebard=False):
    """shield/better_mace/alebard: чи досліджено відповідну технологію
    Кузні (Shields/BetterMaces/Alebards) — вирішує викликач (ui_game.py),
    графіка сама лише перемикає варіант, який малювати."""
    draw_worker(canvas, x1, y1, x2, y2, color_hex, action_points=action_points)
    w, h = x2 - x1, y2 - y1
    top_y, bottom_y = y1 + h * 0.2, y2 - h * 0.08
    wx = x2 - w * 0.2

    if warrior_type == "Sword":
        _draw_sword(canvas, wx, top_y, bottom_y, w, color_hex, shield=shield)
    elif warrior_type == "Mace":
        _draw_mace(canvas, wx, top_y, bottom_y, w, color_hex, better=better_mace)
    elif warrior_type == "Spear":
        _draw_spear(canvas, wx, top_y, bottom_y, w, color_hex, alebard=alebard)


# ---------------------------------------------------------------------------
# Лучник (+ Арбалетник) — та сама постать, інша зброя
# ---------------------------------------------------------------------------

def draw_archer(canvas, x1, y1, x2, y2, color_hex, action_points=2, crossbow=False):
    draw_worker(canvas, x1, y1, x2, y2, color_hex, action_points=action_points)
    w, h = x2 - x1, y2 - y1
    wx = x2 - w * 0.22
    top_y, bottom_y = y1 + h * 0.2, y2 - h * 0.1

    if not crossbow:
        canvas.create_arc(wx - w * 0.14, top_y, wx + w * 0.14, bottom_y,
                           start=260, extent=200, style="arc", outline=COLOR_WOOD, width=max(2, int(w * 0.05)))
        canvas.create_line(wx, top_y + h * 0.02, wx, bottom_y - h * 0.02, fill=color_hex, width=1)
    else:
        my = (top_y + bottom_y) / 2
        canvas.create_line(wx - w * 0.16, my, wx + w * 0.16, my, fill=COLOR_WOOD, width=max(2, int(w * 0.06)))
        canvas.create_line(wx, my - h * 0.14, wx, my + h * 0.02, fill=COLOR_WOOD_DARK, width=max(2, int(w * 0.05)))
        canvas.create_line(wx, my - h * 0.02, wx + w * 0.14, my - h * 0.02, fill=color_hex, width=2)


# ---------------------------------------------------------------------------
# Вершник — 2 руки = 2 AP, 3є AP і сон коня = око коня, Faster Horses = брова
# ---------------------------------------------------------------------------

def draw_horseman(canvas, x1, y1, x2, y2, color_hex, action_points=3, has_faster_horses=False):
    """Вершник = маленький верхній торс (голова+тулуб+2 руки, той самий
    принцип рук, що й у робітника) верхи на голові/шиї коня, БЕЗ окремих
    ніг — рахунок AP цілком передають руки вершника + очі/брова коня, щоб
    силует не розсипався на 2 незалежні постаті."""
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2

    body_ap = min(action_points, 3) if not has_faster_horses else min(max(action_points - 1, 0), 3)
    if has_faster_horses:
        eyebrow_visible = action_points >= 4
        eye_state = "dot" if body_ap >= 3 else ("dash" if action_points <= 0 else "none")
    else:
        eyebrow_visible = False
        eye_state = "dot" if action_points >= 3 else ("dash" if action_points <= 0 else "none")

    # Кінь — велика, чітка голова/шия, займає більшість кадру.
    horse_size = w * 0.85
    horse_cy = y1 + h * 0.6
    _draw_horse_head(canvas, cx, horse_cy, horse_size, color_hex, eye=eye_state)

    if has_faster_horses and eyebrow_visible:
        ex, ey = cx + w * 0.03, horse_cy - horse_size * 0.16 - h * 0.06
        canvas.create_line(ex - w * 0.07, ey, ex + w * 0.07, ey - h * 0.015, fill="black", width=2)

    # Вершник: маленька голова, що сидить на шиї коня, з короткими руками
    # (компактно, щоб не розпадався на 2 окремі постаті в такому малому кадрі).
    rider_r = w * 0.1
    rider_cx = cx - w * 0.04
    rider_cy = horse_cy - horse_size * 0.4
    canvas.create_oval(rider_cx - rider_r, rider_cy - rider_r, rider_cx + rider_r, rider_cy + rider_r,
                        fill=color_hex, outline="black", width=2)

    left_up = min(body_ap, 2) >= 2
    right_up = min(body_ap, 2) >= 1
    arm = w * 0.16
    if left_up:
        canvas.create_line(rider_cx, rider_cy, rider_cx - arm, rider_cy - arm * 0.55, fill="black", width=2)
    else:
        canvas.create_line(rider_cx, rider_cy, rider_cx - arm * 0.75, rider_cy + arm * 0.45, fill="black", width=2)
    if right_up:
        canvas.create_line(rider_cx, rider_cy, rider_cx + arm, rider_cy - arm * 0.55, fill="black", width=2)
    else:
        canvas.create_line(rider_cx, rider_cy, rider_cx + arm * 0.75, rider_cy + arm * 0.45, fill="black", width=2)


# ---------------------------------------------------------------------------
# Маг та слизень
# ---------------------------------------------------------------------------

def draw_mage(canvas, x1, y1, x2, y2, color_hex, action_points=2):
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2

    canvas.create_oval(cx - w * 0.15, y1 + h * 0.3, cx + w * 0.15, y1 + h * 0.56,
                        fill=color_hex, outline="black", width=2)
    canvas.create_polygon(cx, y1 + h * 0.02, cx - w * 0.24, y1 + h * 0.32, cx + w * 0.24, y1 + h * 0.32,
                           fill=color_hex, outline="black", width=2)

    left_up = action_points >= 2
    right_up = action_points >= 1
    shoulder_y = y1 + h * 0.42
    if left_up:
        canvas.create_line(cx - w * 0.15, shoulder_y, cx - w * 0.32, y1 + h * 0.26, fill="black", width=2)
    else:
        canvas.create_line(cx - w * 0.15, shoulder_y, cx - w * 0.28, y1 + h * 0.56, fill="black", width=2)
    if right_up:
        canvas.create_line(cx + w * 0.15, shoulder_y, cx + w * 0.32, y1 + h * 0.26, fill="black", width=2)
    else:
        canvas.create_line(cx + w * 0.15, shoulder_y, cx + w * 0.28, y1 + h * 0.56, fill="black", width=2)

    canvas.create_line(cx, y1 + h * 0.56, cx - w * 0.14, y2 - h * 0.06, fill="black", width=2)
    canvas.create_line(cx, y1 + h * 0.56, cx + w * 0.14, y2 - h * 0.06, fill="black", width=2)

    canvas.create_line(cx + w * 0.3, y1 + h * 0.2, cx + w * 0.3, y2 - h * 0.08, fill=COLOR_WOOD,
                        width=max(2, int(w * 0.05)))
    canvas.create_oval(cx + w * 0.24, y1 + h * 0.1, cx + w * 0.36, y1 + h * 0.22,
                        fill=color_hex, outline="black")


def draw_slime(canvas, x1, y1, x2, y2, color_hex, action_points=1):
    """1 AP (повний) = звичайний розмір, 0 AP = помітно менший (втома)."""
    w, h = x2 - x1, y2 - y1
    cx, base_y = x1 + w / 2, y2 - h * 0.1
    scale = 1.0 if action_points >= 1 else 0.65
    r = w * 0.36 * scale

    canvas.create_polygon(
        cx - r, base_y,
        cx - r, base_y - r * 1.1,
        cx, base_y - r * 1.7,
        cx + r, base_y - r * 1.1,
        cx + r, base_y,
        fill=color_hex, outline="black", width=2, smooth=True,
    )


# ---------------------------------------------------------------------------
# Катапульта, корабель, гарматний човен
# ---------------------------------------------------------------------------

def draw_catapult(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    wheel_r = w * 0.14
    wheel_y = y2 - h * 0.18
    for wx in (x1 + w * 0.24, x2 - w * 0.24):
        canvas.create_oval(wx - wheel_r, wheel_y - wheel_r, wx + wheel_r, wheel_y + wheel_r,
                            fill=COLOR_WOOD, outline="black", width=2)
        canvas.create_oval(wx - wheel_r * 0.3, wheel_y - wheel_r * 0.3, wx + wheel_r * 0.3, wheel_y + wheel_r * 0.3,
                            fill="black", outline="")
    canvas.create_rectangle(x1 + w * 0.2, wheel_y - h * 0.04, x2 - w * 0.2, wheel_y + h * 0.04,
                             fill=color_hex, outline="black", width=2)
    canvas.create_line(x1 + w * 0.28, wheel_y - h * 0.02, x2 - w * 0.15, y1 + h * 0.12,
                        fill=COLOR_WOOD, width=max(3, int(w * 0.08)))
    canvas.create_polygon(x2 - w * 0.28, y1 + h * 0.02, x2 - w * 0.1, y1 + h * 0.1,
                           x2 - w * 0.2, y1 + h * 0.22, fill=COLOR_STONE, outline="black", width=2)


def draw_ship(canvas, x1, y1, x2, y2, color_hex, tired=False):
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    canvas.create_polygon(x1 + w * 0.1, y1 + h * 0.62, x2 - w * 0.1, y1 + h * 0.62,
                           x2 - w * 0.22, y2 - h * 0.1, x1 + w * 0.22, y2 - h * 0.1,
                           fill=COLOR_WOOD, outline="black", width=2)
    canvas.create_line(cx, y1 + h * 0.62, cx, y1 + h * 0.1, fill="#3b2412", width=2)
    if tired:
        canvas.create_polygon(cx, y1 + h * 0.15, cx + w * 0.22, y1 + h * 0.4, cx, y1 + h * 0.4,
                               fill=color_hex, outline="black")
    else:
        canvas.create_polygon(cx, y1 + h * 0.1, cx + w * 0.28, y1 + h * 0.55, cx, y1 + h * 0.55,
                               fill=color_hex, outline="black")


def draw_cannon_boat(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    canvas.create_polygon(x1 + w * 0.08, y1 + h * 0.62, x2 - w * 0.08, y1 + h * 0.62,
                           x2 - w * 0.2, y2 - h * 0.08, x1 + w * 0.2, y2 - h * 0.08,
                           fill=COLOR_WOOD, outline="black", width=2)
    canvas.create_line(x2 - w * 0.36, y1 + h * 0.6, cx, y1 + h * 0.1, fill="#3b2412", width=2)
    canvas.create_polygon(x2 - w * 0.36, y1 + h * 0.6, cx, y1 + h * 0.6, cx, y1 + h * 0.12,
                           fill=color_hex, outline="black")
    canvas.create_rectangle(x1 + w * 0.14, y1 + h * 0.5, x1 + w * 0.4, y1 + h * 0.6,
                             fill=COLOR_STONE, outline="black", width=2)
    canvas.create_oval(x1 + w * 0.06, y1 + h * 0.46, x1 + w * 0.22, y1 + h * 0.62,
                        fill=COLOR_METAL, outline="black", width=2)


# ---------------------------------------------------------------------------
# Снаряди в польоті (керує ui_game.py — анімує позицію вздовж траєкторії)
# ---------------------------------------------------------------------------

def draw_projectile_arrow(canvas, x, y, angle, size, color_hex="black"):
    dx, dy = math.cos(angle), math.sin(angle)
    tail_x, tail_y = x - dx * size, y - dy * size
    canvas.create_line(tail_x, tail_y, x, y, fill=COLOR_WOOD, width=max(1, int(size * 0.14)),
                        arrow="last", arrowshape=(size * 0.5, size * 0.6, size * 0.22))


def draw_projectile_cannonball(canvas, x, y, size, color_hex=None):
    r = size * 0.32
    canvas.create_oval(x - r, y - r, x + r, y + r, fill="#1c1c1c", outline="black")


def draw_projectile_magic_sparkle(canvas, x, y, size, color_hex):
    """4-променева зірка — командного кольору, спільна для ВСІХ заклинань."""
    r_out, r_in = size * 0.4, size * 0.14
    points = []
    for i in range(8):
        r = r_out if i % 2 == 0 else r_in
        angle = i * (math.pi / 4)
        points.extend([x + math.cos(angle) * r, y + math.sin(angle) * r])
    canvas.create_polygon(points, fill=color_hex, outline="black", width=1, smooth=False)


# ---------------------------------------------------------------------------
# Іконки ресурсів (Gold/Wood/Food завжди нейтральні; Horse — командний колір)
# ---------------------------------------------------------------------------

def draw_icon_gold(canvas, x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    cx, cy = x1 + w / 2, y1 + h / 2
    r = min(w, h) * 0.42
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=COLOR_GOLD_YELLOW, outline="#b8860b", width=2)
    canvas.create_rectangle(cx - r * 0.16, cy - r * 0.5, cx + r * 0.16, cy + r * 0.5,
                             fill="#b8860b", outline="")


def draw_icon_wood(canvas, x1, y1, x2, y2):
    """Компактна іконка (не весь тайл лісу) — самотнє дерево без фону."""
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    canvas.create_rectangle(cx - w * 0.06, y1 + h * 0.72, cx + w * 0.06, y2 - h * 0.06,
                             fill=COLOR_TRUNK, outline="black")
    canvas.create_polygon(cx - w * 0.32, y1 + h * 0.78, cx + w * 0.32, y1 + h * 0.78, cx, y1 + h * 0.32,
                           fill=COLOR_TREE, outline="black")
    canvas.create_polygon(cx - w * 0.22, y1 + h * 0.5, cx + w * 0.22, y1 + h * 0.5, cx, y1 + h * 0.1,
                           fill=COLOR_TREE, outline="black")


def draw_icon_food(canvas, x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    canvas.create_polygon(cx - w * 0.34, y1 + h * 0.14, cx + w * 0.34, y1 + h * 0.14,
                           cx + w * 0.12, y1 + h * 0.6, cx + w * 0.12, y2 - h * 0.1,
                           cx - w * 0.12, y2 - h * 0.1, cx - w * 0.12, y1 + h * 0.6,
                           fill=COLOR_GOLD_YELLOW, outline="black", width=2)


def draw_icon_horse(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    _draw_horse_head(canvas, x1 + w / 2, y1 + h / 2, min(w, h) * 0.9, color_hex, eye="dot")


# ---------------------------------------------------------------------------
# Іконки технологій (Кузня повторно використовує спрайт прокачаного юніта)
# ---------------------------------------------------------------------------

def draw_icon_bread(canvas, x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    canvas.create_polygon(x1 + w * 0.1, y2 - h * 0.14, x1 + w * 0.1, y1 + h * 0.5,
                           cx, y1 + h * 0.1, x2 - w * 0.1, y1 + h * 0.5, x2 - w * 0.1, y2 - h * 0.14,
                           fill=COLOR_FIRE, outline="black", width=2, smooth=True)
    for dx in (-0.22, 0, 0.22):
        canvas.create_line(cx + w * dx, y1 + h * 0.28, cx + w * dx, y1 + h * 0.42,
                            fill="#fdf3d7", width=max(2, int(w * 0.05)))


def draw_icon_heavy_artillery(canvas, x1, y1, x2, y2):
    """Не командного кольору (нейтральна іконка технології)."""
    w, h = x2 - x1, y2 - y1
    cx = x1 + w / 2
    canvas.create_rectangle(x1 + w * 0.06, y1 + h * 0.2, cx + w * 0.1, y1 + h * 0.56,
                             fill=COLOR_STONE, outline="black", width=2)
    canvas.create_arc(x2 - w * 0.42, y1 + h * 0.2, x2 - w * 0.06, y1 + h * 0.68,
                       start=270, extent=180, fill=COLOR_STONE, outline="black", width=2, style="chord")
    canvas.create_polygon(cx - w * 0.12, y2 - h * 0.1, cx - w * 0.12, y1 + h * 0.42,
                           cx, y1 + h * 0.28, cx + w * 0.12, y1 + h * 0.42, cx + w * 0.12, y2 - h * 0.1,
                           fill=COLOR_FIRE, outline="black", width=2)


def draw_icon_armored_towers(canvas, x1, y1, x2, y2, color_hex):
    """Звичайна прокачана вежа (тут — без конкретного типу, лише
    заброньована основа), як просив Саша."""
    draw_tower(canvas, x1, y1, x2, y2, color_hex, tower_type="ArcherTower", armored=True)


# ---------------------------------------------------------------------------
# Іконки заклинань (усі, крім Heal/Freeze/MagicShield/Slime, — фон-об'єкт
# + командного кольору "вибух")
# ---------------------------------------------------------------------------

def draw_icon_heal(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    cx, cy = x1 + w / 2, y1 + h * 0.45
    r = w * 0.22
    canvas.create_polygon(
        cx, y1 + h * 0.78,
        cx - w * 0.36, y1 + h * 0.34,
        cx - w * 0.36, y1 + h * 0.1, cx - w * 0.12, y1 + h * 0.02, cx, y1 + h * 0.2,
        cx + w * 0.12, y1 + h * 0.02, cx + w * 0.36, y1 + h * 0.1, cx + w * 0.36, y1 + h * 0.34,
        fill=color_hex, outline="black", width=2, smooth=True,
    )


def draw_icon_freeze(canvas, x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    cx, cy = x1 + w / 2, y1 + h / 2
    r = min(w, h) * 0.4
    for i in range(3):
        angle = i * (math.pi / 3)
        dx, dy = math.cos(angle) * r, math.sin(angle) * r
        canvas.create_line(cx - dx, cy - dy, cx + dx, cy + dy, fill="#74d3ff", width=max(2, int(w * 0.06)))


def draw_icon_magic_shield(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    cx, cy = x1 + w / 2, y1 + h / 2
    r = min(w, h) * 0.4
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color_hex, width=max(2, int(w * 0.07)),
                        stipple="gray50")


def draw_icon_bridge_gone(canvas, x1, y1, x2, y2, color_hex):
    """You Shall Not Pass: міст на задньому плані + зірка-вибух командного кольору спереду."""
    draw_bridge_horizontal(canvas, x1, y1, x2, y2)
    w, h = x2 - x1, y2 - y1
    draw_projectile_magic_sparkle(canvas, x1 + w / 2, y1 + h / 2, min(w, h) * 1.1, color_hex)


def draw_icon_thunder(canvas, x1, y1, x2, y2, color_hex):
    """Thunder: човен на задньому плані + зірка-вибух командного кольору спереду."""
    draw_ship(canvas, x1, y1, x2, y2, "#95a5a6", tired=False)
    w, h = x2 - x1, y2 - y1
    draw_projectile_magic_sparkle(canvas, x1 + w * 0.62, y1 + h * 0.4, min(w, h) * 0.9, color_hex)


def draw_icon_teleport(canvas, x1, y1, x2, y2, color_hex):
    w, h = x2 - x1, y2 - y1
    cx, cy = x1 + w / 2, y1 + h / 2
    canvas.create_polygon(
        cx - w * 0.32, cy - h * 0.1, cx + w * 0.05, cy - h * 0.1, cx + w * 0.05, cy - h * 0.26,
        cx + w * 0.34, cy, cx + w * 0.05, cy + h * 0.26, cx + w * 0.05, cy + h * 0.1,
        cx - w * 0.32, cy + h * 0.1,
        fill=color_hex, outline="black", width=2,
    )


def draw_icon_summon_slime(canvas, x1, y1, x2, y2, color_hex):
    draw_slime(canvas, x1, y1, x2, y2, color_hex, action_points=1)
