"""
Little Kingdoms — панель "Play locally" (налаштування нової локальної гри).
"""

import tkinter as tk
from tkinter import messagebox

from config import PLAYER_COLORS
from ui_widgets import RoundedButton, RoundedPanel, SmallIconButton, ColorPickerPopup, fg_for_color, CARD_COLOR

MIN_MAP_SIZE = 8
MAX_MAP_SIZE = 24

MIN_PLAYERS = 1
MAX_PLAYERS = 8

WATER_MODES = ["No water", "Rivers", "Lakes", "Islands"]

PANEL_WIDTH = 560
PANEL_HEIGHT = 740


class PlayLocallySetupPanel(tk.Frame):
    """Вміст панелі Play locally із фіксованою висотою."""

    def __init__(self, master, app, on_close, **kwargs):
        super().__init__(master, bg=CARD_COLOR, width=PANEL_WIDTH, height=PANEL_HEIGHT, **kwargs)
        
        # Забороняємо дочірнім елементам змінювати фіксований розмір панелі
        self.pack_propagate(False)

        self.app = app
        self.on_close = on_close

        self.players = [
            {"type": "Human", "color": "Blue"},
            {"type": "Human", "color": "Red"},
        ]

        self._build_header()
        self._build_size_and_type()
        self._build_map_code_row()

        self.players_container = tk.Frame(self, bg=CARD_COLOR)
        self.players_container.pack(pady=(4, 4))
        self._render_player_table()

        self._build_start_button()

    # ------------------------------------------------------------------
    # Заголовок з кнопкою закриття
    # ------------------------------------------------------------------
    def _build_header(self):
        header = tk.Frame(self, bg=CARD_COLOR)
        header.pack(fill="x", pady=(8, 4), padx=14)

        SmallIconButton(header, "X", self.on_close, size=32, bg="#c0392b", shape="square").pack(side="left")
        tk.Label(header, text="Play locally", bg=CARD_COLOR, fg="#2c3e50",
                 font=("Arial", 22, "bold")).pack(side="left", expand=True)
        tk.Frame(header, bg=CARD_COLOR, width=32, height=1).pack(side="left")

    # ------------------------------------------------------------------
    # Розмір мапи + тип мапи
    # ------------------------------------------------------------------
    def _build_size_and_type(self):
        row = tk.Frame(self, bg=CARD_COLOR)
        row.pack(pady=(2, 6))

        size_panel = RoundedPanel(row, width=230, height=120)
        size_panel.grid(row=0, column=0, padx=8)
        tk.Label(size_panel.body, text="Map Size", bg=CARD_COLOR, fg="#2c3e50",
                 font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=4, pady=(2, 4))

        tk.Label(size_panel.body, text="X:", bg=CARD_COLOR, fg="#2c3e50",
                 font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="e", padx=4)
        self.entry_x = tk.Entry(size_panel.body, width=5, font=("Arial", 11), justify="center", relief="solid", bd=1)
        self.entry_x.insert(0, "12")
        self.entry_x.grid(row=1, column=1, padx=(0, 10))

        tk.Label(size_panel.body, text="Y:", bg=CARD_COLOR, fg="#2c3e50",
                 font=("Arial", 10, "bold")).grid(row=1, column=2, sticky="e", padx=4)
        self.entry_y = tk.Entry(size_panel.body, width=5, font=("Arial", 11), justify="center", relief="solid", bd=1)
        self.entry_y.insert(0, "12")
        self.entry_y.grid(row=1, column=3)

        tk.Label(size_panel.body, text=f"({MIN_MAP_SIZE} to {MAX_MAP_SIZE})", bg=CARD_COLOR, fg="#7f8c8d",
                 font=("Arial", 8)).grid(row=2, column=0, columnspan=4, pady=(4, 0))

        type_panel = RoundedPanel(row, width=190, height=120)
        type_panel.grid(row=0, column=1, padx=8)
        tk.Label(type_panel.body, text="Map type", bg=CARD_COLOR, fg="#2c3e50",
                 font=("Arial", 12, "bold")).pack(pady=(2, 4))

        list_border = tk.Frame(type_panel.body, bg="#bdc3c7", padx=1, pady=1)
        list_border.pack()
        self.water_listbox = tk.Listbox(
            list_border, height=len(WATER_MODES), width=14, font=("Arial", 10),
            exportselection=False, relief="flat", justify="center",
            selectbackground="#74b9ff", activestyle="none", bd=0,
        )
        for mode in WATER_MODES:
            self.water_listbox.insert("end", mode)
        self.water_listbox.selection_set(0)
        self.water_listbox.pack()

    # ------------------------------------------------------------------
    # Map code + Import
    # ------------------------------------------------------------------
    def _build_map_code_row(self):
        row = tk.Frame(self, bg=CARD_COLOR)
        row.pack(pady=(0, 4))

        self.map_code_entry = tk.Entry(row, width=34, font=("Arial", 10), relief="solid", bd=1)
        self.map_code_entry.pack(side="left", padx=(0, 8), ipady=2)

        RoundedButton(
            row, text="Import", command=self._on_import_clicked, width=100, height=30,
            radius=10, bg="#27ae60", hover_bg="#2ecc71", font=("Arial", 10, "bold"),
        ).pack(side="left")

    def _on_import_clicked(self):
        messagebox.showinfo("Little Kingdoms", "Імпорт мапи буде доступний після Map Creator.")

    # ------------------------------------------------------------------
    # Таблиця гравців
    # ------------------------------------------------------------------
    def _render_player_table(self):
        for widget in self.players_container.winfo_children():
            widget.destroy()

        panel_height = 50 * len(self.players) + 40
        panel = RoundedPanel(self.players_container, width=430, height=panel_height)
        panel.grid(row=0, column=0)

        for idx, player in enumerate(self.players):
            self._render_player_row(panel.body, idx, player)

        if len(self.players) < MAX_PLAYERS:
            add_row = tk.Frame(panel.body, bg=CARD_COLOR)
            add_row.pack(pady=(4, 2))
            SmallIconButton(add_row, "+", self._add_player, size=28, bg="#27ae60").pack()

    def _render_player_row(self, parent, idx, player):
        row = tk.Frame(parent, bg=CARD_COLOR)
        row.pack(pady=2)

        tk.Label(row, text=f"P{idx + 1}", font=("Arial", 11, "bold"), bg="#ecf0f1",
                 fg="#2c3e50", width=4, height=1, relief="flat").grid(row=0, column=0, padx=(0, 6))

        RoundedButton(
            row, text=player["type"], command=lambda i=idx: self._toggle_player_type(i),
            width=90, height=36, radius=8, bg="#95a5a6", hover_bg="#7f8c8d",
            font=("Arial", 10, "bold"),
        ).grid(row=0, column=1, padx=4)

        color_hex = PLAYER_COLORS.get(player["color"], "#bdc3c7") if player["color"] else "#bdc3c7"
        RoundedButton(
            row, text=(player["color"] or "Color"), command=lambda i=idx, r=row: self._open_color_picker(i, r),
            width=100, height=36, radius=8, bg=color_hex, hover_bg=color_hex,
            fg=fg_for_color(player["color"]) if player["color"] else "black",
            font=("Arial", 10, "bold"),
        ).grid(row=0, column=2, padx=4)

        if len(self.players) > MIN_PLAYERS:
            SmallIconButton(row, "x", lambda i=idx: self._remove_player(i),
                             size=24, bg="#e74c3c", shape="square").grid(row=0, column=3, padx=(6, 0))

    def _add_player(self):
        if len(self.players) >= MAX_PLAYERS:
            return
        used_colors = {p["color"] for p in self.players if p["color"]}
        free_color = next((c for c in PLAYER_COLORS if c not in used_colors), None)
        self.players.append({"type": "Human", "color": free_color})
        self._render_player_table()

    def _remove_player(self, idx):
        if len(self.players) <= MIN_PLAYERS:
            return
        del self.players[idx]
        self._render_player_table()

    def _toggle_player_type(self, idx):
        current = self.players[idx]["type"]
        self.players[idx]["type"] = "Bot" if current == "Human" else "Human"
        self._render_player_table()

    def _open_color_picker(self, idx, anchor_widget):
        owner_by_color = {
            p["color"]: i for i, p in enumerate(self.players) if i != idx and p["color"]
        }
        current_color = self.players[idx]["color"]

        def on_pick(picked_color):
            if picked_color == current_color:
                return
            other_idx = owner_by_color.get(picked_color)
            if other_idx is not None:
                self.players[other_idx]["color"] = current_color
            self.players[idx]["color"] = picked_color
            self._render_player_table()

        popup = ColorPickerPopup(self, current_color, owner_by_color, on_pick)
        x = anchor_widget.winfo_rootx() + anchor_widget.winfo_width()
        y = anchor_widget.winfo_rooty()
        popup.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Валідація та запуск гри
    # ------------------------------------------------------------------
    def _build_start_button(self):
        RoundedButton(
            self, text="Start", command=self._on_start_clicked,
            width=PANEL_WIDTH - 60, height=48, radius=14,
            bg="#27ae60", hover_bg="#2ecc71", font=("Arial", 16, "bold"),
        ).pack(pady=(4, 10))

    def _on_start_clicked(self):
        settings, error = self._collect_and_validate()
        if error:
            messagebox.showerror("Little Kingdoms", error)
            return
        self.app.on_menu_confirmed(settings)

    def _collect_and_validate(self):
        try:
            width = int(self.entry_x.get())
            height = int(self.entry_y.get())
        except ValueError:
            return None, "Map size X and Y must be whole numbers."

        if not (MIN_MAP_SIZE <= width <= MAX_MAP_SIZE):
            return None, f"Map width (X) must be between {MIN_MAP_SIZE} and {MAX_MAP_SIZE}."
        if not (MIN_MAP_SIZE <= height <= MAX_MAP_SIZE):
            return None, f"Map height (Y) must be between {MIN_MAP_SIZE} and {MAX_MAP_SIZE}."

        selection = self.water_listbox.curselection()
        if not selection:
            return None, "Please choose a map type."
        water_mode = self.water_listbox.get(selection[0])

        if not (MIN_PLAYERS <= len(self.players) <= MAX_PLAYERS):
            return None, f"Number of players must be between {MIN_PLAYERS} and {MAX_PLAYERS}."

        for idx, player in enumerate(self.players):
            if not player["color"]:
                return None, f"Choose a color for player P{idx + 1}."

        colors_used = [p["color"] for p in self.players]
        if len(colors_used) != len(set(colors_used)):
            return None, "Player colors cannot repeat."

        settings = {
            "map_width": width,
            "map_height": height,
            "water_mode": water_mode,
            "players": [
                {"id": idx, "type": p["type"], "color": p["color"]}
                for idx, p in enumerate(self.players)
            ],
        }
        return settings, None
