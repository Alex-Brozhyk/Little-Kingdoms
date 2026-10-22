"""
Little Kingdoms — генерація ігрового світу.

Модуль повністю не залежить від tkinter: приймає розміри та тип води,
повертає двовимірну сітку тайлів (список списків рядків) та список замків.
Завдяки цьому генерацію можна тестувати окремо, без відкриття вікна.

Правила генерації (за ТЗ):
    * Rivers: 40% горизонтальна, 40% вертикальна, 20% "потрійна" річка.
    * Islands: 25% шанс на 1 острів, 25% на 2, 25% на 3, 25% на 4.
      Кожна окрема ділянка суші (landmass) повинна мати ХОЧА Б 1 тайл
      кожного ресурсу (Forest / Wheat / Mountain), більші ділянки — більше.
    * Замки гравців: мінімум 4 клітинки відстані між замками,
      по можливості кожен замок — у своїй чверті мапи.

TODO: коли з'явиться config.py, перенести MIN_CASTLE_DISTANCE
та параметри щільності ресурсів туди для легкого ребалансу.
"""

import random

# ---------------------------------------------------------------------------
# Типи тайлів
# ---------------------------------------------------------------------------

TILE_GRASS = "grass"
TILE_FOREST = "forest"
TILE_WHEAT = "wheat"
TILE_MOUNTAIN = "mountain"
TILE_WATER = "water"

WATER_MODE_NONE = "No water"
WATER_MODE_RIVERS = "Rivers"
WATER_MODE_LAKES = "Lakes"
WATER_MODE_ISLANDS = "Islands"

MIN_CASTLE_DISTANCE = 4  # мінімальна відстань (по кожній осі) між замками

# Порядок чвертей мапи: верх-ліво, верх-право, низ-право, низ-ліво.
_QUADRANT_ORDER = [(0, 0), (0, 1), (1, 1), (1, 0)]


# ---------------------------------------------------------------------------
# Публічне API
# ---------------------------------------------------------------------------

def generate_world(width, height, water_mode):
    """Генерує сітку тайлів width x height відповідно до типу води.

    Повертає grid[row][col] -> один з TILE_* констант.
    """
    if water_mode == WATER_MODE_RIVERS:
        grid = _generate_grass_base(width, height)
        _carve_rivers(grid, width, height)
    elif water_mode == WATER_MODE_LAKES:
        grid = _generate_grass_base(width, height)
        _carve_lakes(grid, width, height)
    elif water_mode == WATER_MODE_ISLANDS:
        grid = _generate_islands(width, height)
    else:  # No water
        grid = _generate_grass_base(width, height)

    _populate_resources(grid, width, height)
    return grid


def place_castles(grid, width, height, players):
    """Розставляє замки гравців на тайлах трави.

    Повертає список словників: {"row", "col", "owner_id", "color"}.
    Кожен замок намагається потрапити у власну чверть мапи,
    з мінімальною відстанню MIN_CASTLE_DISTANCE від інших замків.
    """
    num_players = len(players)
    quadrants = _pick_quadrants(num_players)

    castles = []
    placed_positions = []

    for player, (qrow, qcol) in zip(players, quadrants):
        pos = _find_castle_spot(grid, width, height, qrow, qcol, placed_positions)
        placed_positions.append(pos)
        castles.append({
            "row": pos[0],
            "col": pos[1],
            "owner_id": player["id"],
            "color": player["color"],
        })

    return castles


# ---------------------------------------------------------------------------
# Базова сітка та вода
# ---------------------------------------------------------------------------

def _generate_grass_base(width, height):
    return [[TILE_GRASS for _ in range(width)] for _ in range(height)]


def _carve_rivers(grid, width, height):
    river_type = random.choices(
        ["horizontal", "vertical", "triple", "diag_forward", "diag_backward"],
        weights=[0.2, 0.2, 0.2, 0.2, 0.2],
    )[0]

    if river_type in ("horizontal", "triple"):
        _carve_horizontal_river(grid, width, height)
    if river_type in ("vertical", "triple"):
        _carve_vertical_river(grid, width, height)
    if river_type == "diag_forward":
        _carve_diagonal_river(grid, width, height, forward=True)
    if river_type == "diag_backward":
        _carve_diagonal_river(grid, width, height, forward=False)


def _carve_horizontal_river(grid, width, height):
    # Річка тримається середньої смуги мапи (40-60% висоти), щоб ділити
    # мапу приблизно навпіл, а не проходити близько до краю.
    band_lo = max(1, int(height * 0.4))
    band_hi = min(height - 2, int(height * 0.6))
    if band_hi < band_lo:
        band_lo, band_hi = 1, max(1, height - 2)
    cy = random.randint(band_lo, band_hi)

    for x in range(width):
        grid[cy][x] = TILE_WATER
        if cy + 1 < height:
            grid[cy + 1][x] = TILE_WATER
        cy = max(band_lo, min(band_hi, cy + random.choice([-1, 0, 1])))


def _carve_vertical_river(grid, width, height):
    band_lo = max(1, int(width * 0.4))
    band_hi = min(width - 2, int(width * 0.6))
    if band_hi < band_lo:
        band_lo, band_hi = 1, max(1, width - 2)
    cx = random.randint(band_lo, band_hi)

    for y in range(height):
        grid[y][cx] = TILE_WATER
        if cx + 1 < width:
            grid[y][cx + 1] = TILE_WATER
        cx = max(band_lo, min(band_hi, cx + random.choice([-1, 0, 1])))


def _carve_diagonal_river(grid, width, height, forward):
    """Річка від одного краю мапи до іншого по діагоналі.
    forward=True  -> "/" (від нижнього-лівого до верхнього-правого кута)
    forward=False -> "\\" (від верхнього-лівого до нижнього-правого кута)
    """
    jitter = 0
    for c in range(width):
        t = c / max(1, width - 1)
        ideal_r = (height - 1) * (1 - t) if forward else (height - 1) * t
        jitter = max(-1, min(1, jitter + random.choice([-1, 0, 0, 1])))
        r = max(0, min(height - 1, int(round(ideal_r)) + jitter))

        grid[r][c] = TILE_WATER
        r2 = r + 1 if r + 1 < height else r - 1
        grid[r2][c] = TILE_WATER


def _carve_lakes(grid, width, height):
    area = width * height
    num_lakes = random.randint(2, max(3, area // 150))
    for _ in range(num_lakes):
        cx = random.randint(2, max(2, width - 3))
        cy = random.randint(2, max(2, height - 3))
        radius = random.randint(1, 3)
        for r in range(cy - radius, cy + radius + 1):
            for c in range(cx - radius, cx + radius + 1):
                if 0 <= r < height and 0 <= c < width:
                    if (r - cy) ** 2 + (c - cx) ** 2 <= radius ** 2 + random.randint(-1, 1):
                        grid[r][c] = TILE_WATER


def _generate_islands(width, height):
    grid = [[TILE_WATER for _ in range(width)] for _ in range(height)]

    # 25% / 25% / 25% / 25% на 1..4 острови.
    num_islands = random.choices([1, 2, 3, 4], weights=[0.25, 0.25, 0.25, 0.25])[0]
    quadrants = _pick_quadrants(num_islands)

    centers = []
    for (qrow, qcol) in quadrants:
        r0, r1, c0, c1 = _quadrant_bounds(width, height, qrow, qcol, margin=3)
        cx = random.randint(c0, c1)
        cy = random.randint(r0, r1)
        centers.append((cx, cy))

    for cx, cy in centers:
        radius = random.randint(2, max(3, min(width, height) // 3))
        for r in range(height):
            for c in range(width):
                dist = ((r - cy) ** 2 + (c - cx) ** 2) ** 0.5
                if dist < radius + random.uniform(-0.8, 0.8):
                    grid[r][c] = TILE_GRASS

    return grid


# ---------------------------------------------------------------------------
# Гарантований розподіл ресурсів (flood fill по кожній ділянці суші)
# ---------------------------------------------------------------------------

def _populate_resources(grid, width, height):
    visited = [[False] * width for _ in range(height)]

    for r in range(height):
        for c in range(width):
            if grid[r][c] == TILE_WATER or visited[r][c]:
                continue

            landmass = _flood_fill_landmass(grid, visited, r, c, width, height)
            total_tiles = len(landmass)

            # Мінімум 1 кожного ресурсу, більше — за площею ділянки.
            num_mountains = max(1, total_tiles // 12)
            num_forests = max(1, total_tiles // 8)
            num_wheat = max(1, total_tiles // 10)

            available = landmass.copy()
            random.shuffle(available)

            for _ in range(min(num_mountains, len(available))):
                pos = available.pop()
                grid[pos[0]][pos[1]] = TILE_MOUNTAIN
            for _ in range(min(num_forests, len(available))):
                pos = available.pop()
                grid[pos[0]][pos[1]] = TILE_FOREST
            for _ in range(min(num_wheat, len(available))):
                pos = available.pop()
                grid[pos[0]][pos[1]] = TILE_WHEAT


def _flood_fill_landmass(grid, visited, start_r, start_c, width, height):
    landmass = []
    queue = [(start_r, start_c)]
    visited[start_r][start_c] = True

    while queue:
        r, c = queue.pop(0)
        landmass.append((r, c))
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < height and 0 <= nc < width and not visited[nr][nc]:
                if grid[nr][nc] != TILE_WATER:
                    visited[nr][nc] = True
                    queue.append((nr, nc))

    return landmass


# ---------------------------------------------------------------------------
# Розстановка замків
# ---------------------------------------------------------------------------

def _pick_quadrants(count):
    if count == 2:
        # Діагональні чверті — максимальна відстань для 2 гравців.
        return [_QUADRANT_ORDER[0], _QUADRANT_ORDER[2]]
    if count <= 4:
        return _QUADRANT_ORDER[:count]
    # Понад 4 гравці (до 8) — циклічно повторюємо чверті; фактичне
    # розведення забезпечує MIN_CASTLE_DISTANCE у _find_castle_spot
    # (пробує чверть, тоді всю мапу, тоді послаблює дистанцію).
    return [_QUADRANT_ORDER[i % 4] for i in range(count)]


def _quadrant_bounds(width, height, qrow, qcol, margin=2):
    half_w, half_h = width // 2, height // 2
    c0 = margin if qcol == 0 else half_w
    c1 = (half_w - 1) if qcol == 0 else (width - 1 - margin)
    r0 = margin if qrow == 0 else half_h
    r1 = (half_h - 1) if qrow == 0 else (height - 1 - margin)

    # Захист для дуже малих мап: не даємо порожній діапазон.
    c0, c1 = min(c0, width - 1), max(c1, min(c0, width - 1))
    r0, r1 = min(r0, height - 1), max(r1, min(r0, height - 1))
    return r0, r1, c0, c1


def _find_castle_spot(grid, width, height, qrow, qcol, placed_positions):
    r0, r1, c0, c1 = _quadrant_bounds(width, height, qrow, qcol)

    # 1. Пробуємо знайти травʼяний тайл у своїй чверті з дотриманням дистанції.
    for _ in range(200):
        r = random.randint(r0, r1)
        c = random.randint(c0, c1)
        if grid[r][c] == TILE_GRASS and _far_enough(r, c, placed_positions, MIN_CASTLE_DISTANCE):
            return (r, c)

    # 2. Фолбек: будь-який травʼяний тайл на мапі з дотриманням дистанції.
    all_grass = [(r, c) for r in range(height) for c in range(width) if grid[r][c] == TILE_GRASS]
    random.shuffle(all_grass)
    for r, c in all_grass:
        if _far_enough(r, c, placed_positions, MIN_CASTLE_DISTANCE):
            return (r, c)

    # 3. Останній фолбек: послаблюємо дистанцію, аби гарантовано щось повернути.
    for min_dist in range(MIN_CASTLE_DISTANCE - 1, 0, -1):
        for r, c in all_grass:
            if _far_enough(r, c, placed_positions, min_dist):
                return (r, c)

    return all_grass[0] if all_grass else (0, 0)


def _far_enough(r, c, placed_positions, min_dist):
    for pr, pc in placed_positions:
        if max(abs(r - pr), abs(c - pc)) < min_dist:
            return False
    return True


# ---------------------------------------------------------------------------
# Текстовий самотест (без tkinter) — python3 world_gen.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    SYMBOLS = {
        TILE_GRASS: ".",
        TILE_FOREST: "F",
        TILE_WHEAT: "W",
        TILE_MOUNTAIN: "M",
        TILE_WATER: "~",
    }

    demo_players = [
        {"id": 0, "type": "Human", "color": "Blue"},
        {"id": 1, "type": "Human", "color": "Red"},
        {"id": 2, "type": "Bot", "color": "Green"},
    ]

    for mode in (WATER_MODE_NONE, WATER_MODE_RIVERS, WATER_MODE_LAKES, WATER_MODE_ISLANDS):
        print(f"\n=== {mode} ===")
        g = generate_world(20, 14, mode)
        castles = place_castles(g, 20, 14, demo_players)
        castle_positions = {(c["row"], c["col"]): idx for idx, c in enumerate(castles)}

        for r, row in enumerate(g):
            line = ""
            for c, tile in enumerate(row):
                if (r, c) in castle_positions:
                    line += str(castle_positions[(r, c)])
                else:
                    line += SYMBOLS[tile]
            print(line)
