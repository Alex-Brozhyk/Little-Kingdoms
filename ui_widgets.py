"""
Little Kingdoms — спільні UI-примітиви для меню.

Це набір "красивих" tkinter-віджетів (заокруглені кнопки, картки з
тінню, попап вибору кольору), які використовуються і в ui_menu.py
(головне меню), і в ui_setup.py (панель Play Locally), щоб не
дублювати той самий код кнопок/карток у кожному екрані.

Важливо: RoundedButton / RoundedPanel / SmallIconButton — це окремі
tk.Canvas, чий власний фон (bg=master["bg"]) МАЄ збігатися з фоном
свого безпосереднього батька, інакше по кутах буде видно прямокутну
"пляму" замість заокруглення. Тому їх можна вільно використовувати
всередині вже суцільно білих карток (CARD_COLOR), але НЕ можна класти
напряму на анімований фон мапи — для цього MenuScreen сам малює
заокруглений прямокутник карти прямо на своєму canvas і вбудовує
Frame через create_window (див. ui_menu.py).
"""

import tkinter as tk

from config import PLAYER_COLORS

CARD_COLOR = "#ffffff"
CARD_SHADOW = "#2c2c2c"


def fg_for_color(color_name):
    """Обирає читабельний колір тексту для фону відповідного кольору гравця."""
    return "black" if color_name in ("White", "Yellow") else "white"


def draw_rounded_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class RoundedButton(tk.Canvas):
    """Кнопка із заокругленими кутами, намальована на Canvas, з ефектом
    підсвітки при наведенні (hover_bg)."""

    def __init__(self, master, text, command, width=200, height=64,
                 radius=16, bg="#27ae60", fg="white", font=("Arial", 16, "bold"),
                 hover_bg=None, **kwargs):
        super().__init__(master, width=width, height=height,
                          bg=master["bg"], highlightthickness=0, **kwargs)
        self.command = command
        self.bg = bg
        self.hover_bg = hover_bg or bg

        self._shape = draw_rounded_rect(self, 2, 2, width - 2, height - 2, radius, fill=bg, outline="")
        self._label = self.create_text(width / 2, height / 2, text=text, fill=fg, font=font)

        for tag in (self._shape, self._label):
            self.tag_bind(tag, "<Button-1>", self._on_click)
            self.tag_bind(tag, "<Enter>", self._on_enter)
            self.tag_bind(tag, "<Leave>", self._on_leave)

    def _on_click(self, event):
        if self.command:
            self.command()

    def _on_enter(self, event):
        self.itemconfig(self._shape, fill=self.hover_bg)

    def _on_leave(self, event):
        self.itemconfig(self._shape, fill=self.bg)

    def set_text(self, text):
        self.itemconfig(self._label, text=text)


class SmallIconButton(tk.Canvas):
    """Маленька кругла/квадратна кнопка для '+' та 'x'."""

    def __init__(self, master, symbol, command, size=32, bg="#27ae60", fg="white", shape="circle", **kwargs):
        super().__init__(master, width=size, height=size, bg=master["bg"],
                          highlightthickness=0, **kwargs)
        self.command = command
        if shape == "circle":
            shape_id = self.create_oval(2, 2, size - 2, size - 2, fill=bg, outline="")
        else:
            shape_id = draw_rounded_rect(self, 2, 2, size - 2, size - 2, 6, fill=bg, outline="")
        label_id = self.create_text(size / 2, size / 2, text=symbol, fill=fg, font=("Arial", int(size * 0.5), "bold"))

        for tag in (shape_id, label_id):
            self.tag_bind(tag, "<Button-1>", lambda e: self.command())


class RoundedPanel(tk.Canvas):
    """Біла картка із заокругленими кутами й легкою тінню.

    Внутрішній вміст пакується у self.body (звичайний tk.Frame).
    Використовується для ВКЛАДЕНИХ карток (напр. "Map Size" всередині
    панелі Play locally) — там її власний bg=master["bg"] коректно
    збігається з батьком, бо той теж суцільно білий.
    """

    def __init__(self, master, width, height, radius=20, bg=CARD_COLOR, **kwargs):
        super().__init__(master, width=width, height=height, bg=master["bg"],
                          highlightthickness=0, **kwargs)
        _draw_shadow = draw_rounded_rect(self, 4, 6, width - 2, height + 2, radius, fill="#d0d0d0", outline="")
        draw_rounded_rect(self, 2, 2, width - 6, height - 4, radius, fill=bg, outline="")

        self.body = tk.Frame(self, bg=bg)
        self.create_window((width - 6) / 2, (height - 4) / 2, window=self.body)


class ColorPickerPopup(tk.Toplevel):
    """Спливаюче вікно вибору кольору. Клік по зайнятому кольору = swap
    (гравці міняються кольорами місцями, ніхто не втрачає свій вибір)."""

    def __init__(self, master, current_color, owner_by_color, on_pick):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(bg="#16324f")
        self.on_pick = on_pick

        frame = tk.Frame(self, bg="#16324f", padx=8, pady=8)
        frame.pack()

        for name, hex_color in PLAYER_COLORS.items():
            owner_idx = owner_by_color.get(name)
            label = name
            if owner_idx is not None:
                label = f"{name}  (swap with P{owner_idx + 1})"
            elif name == current_color:
                label = f"{name}  \u2713"

            btn = RoundedButton(
                frame, text=label, command=lambda n=name: self._pick(n),
                width=190, height=34, radius=10, bg=hex_color,
                hover_bg=hex_color, fg=fg_for_color(name), font=("Arial", 10, "bold"),
            )
            btn.pack(pady=2)

        self.bind("<FocusOut>", lambda e: self.destroy())
        self.after(50, lambda: self.focus_set())

    def _pick(self, name):
        self.on_pick(name)
        self.destroy()
