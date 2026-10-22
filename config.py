"""
Little Kingdoms — баланс гри (Beta).

Усі числа (ціни, здоровʼя, атака, виробництво ресурсів) зібрані тут
для легкого ребалансу без правок логіки чи графіки.

Ціна завжди словник {"gold":.., "wood":.., "food":..}; ресурс, який
не використовується для конкретної речі, дорівнює 0 і просто не
показується в підказках.

ВАЖЛИВО — єдине значення, якого й досі немає в ТЗ (позначене TODO
нижче): ціна технології Faster Horses (Стайня). Поставлений орієнтовний
плейсхолдер — треба підтвердити або поправити.
"""

from collections import OrderedDict

# ---------------------------------------------------------------------------
# Гравці
# ---------------------------------------------------------------------------

STARTING_RESOURCES = {"gold": 10, "wood": 10, "food": 10}

PLAYER_COLORS = OrderedDict([
    ("Blue", "#2980b9"),
    ("Red", "#e74c3c"),
    ("Yellow", "#f1c40f"),
    ("Green", "#27ae60"),
    ("White", "#ecf0f1"),
    ("Black", "#1c1c1c"),
    ("Orange", "#e67e22"),
    ("Purple", "#8e44ad"),
])

# ---------------------------------------------------------------------------
# Очки дії (Action Points)
# ---------------------------------------------------------------------------
# Worker/Warrior/Archer/Mage/Slime: власний action_points пул, скидається
# на початку ходу власника. Horseman має БІЛЬШИЙ власний пул (той самий
# принцип: 1 очко = похід, 2 = атака, виснажується як завжди, коли AP<=0).
# Catapult/CannonBoat мають лише 1 очко (похід АБО атака, не обидва).
# Ship лишається на прапорці tired (один рух/дія за хід, без AP-пулу).

UNIT_ACTION_POINTS = 2                # Worker, Warrior, Archer, Mage, Slime
HORSEMAN_ACTION_POINTS = 3            # 5.5.7 — власний, більший пул
FASTER_HORSES_BONUS_AP = 1            # технологія Стайні: +1 до пулу вершника
CATAPULT_ACTION_POINTS = 1            # похід АБО атака
CANNON_BOAT_ACTION_POINTS = 1         # похід АБО атака

ACTION_COST_MOVE = 1
ACTION_COST_BUILD = 2
ACTION_COST_REPAIR = 2
ACTION_COST_STEAL = 2                 # 5.1 крадіжка ресурсів
ACTION_COST_SPELL = 2                 # 5.5.4 — усі заклинання мага
BREAD_ACTION_COST = 1                 # тех. "Хліб": будівництво/ремонт/крадіжка коштують 1 замість 2

# Атака: меч легкий — 1 очко (можна вдарити двічі), булава/спис — 2 очки.
# Worker: 2 очки (баг 1.4 — раніше було 1). Archer/Horseman: атака теж 2 очки
# (у вершника похід коштує 1, атака 2 — саме як описано в 5.5.7).
ATTACK_AP_COST = {
    "Sword": 1, "Mace": 2, "Spear": 2,
    "Worker": 2, "Archer": 2, "Horseman": 2, "Mage": 2, "Slime": 1,
}

# ---------------------------------------------------------------------------
# Робітник
# ---------------------------------------------------------------------------

WORKER_HP = 2
WORKER_ATTACK_VS_UNIT = 1
WORKER_HIRE_COST = {"gold": 0, "wood": 0, "food": 3}
WORKER_REPAIR_COST = {"gold": 1, "wood": 1, "food": 1}
WORKER_REPAIR_AMOUNT = 3              # баг 1.7 — було 5
WORKER_REPAIR_AMOUNT_UPGRADED = 5     # тех. "Better Repair" (Шахта)

# ---------------------------------------------------------------------------
# Воїни (Мечник / Булава / Спис) — 5.5.5 rework: у кожного своя ціна
# ---------------------------------------------------------------------------

WARRIOR_HP = 6
WARRIOR_TYPES = ("Sword", "Mace", "Spear")
WARRIOR_COSTS = {
    "Sword": {"gold": 3, "wood": 0, "food": 3},
    "Spear": {"gold": 1, "wood": 2, "food": 3},
    "Mace":  {"gold": 2, "wood": 0, "food": 4},
}

# WARRIOR_DAMAGE[атакуючий][захисник] -> шкода. Камінь-ножиці-папір:
# Sword>Mace(6) / Mace>Spear(6) / Spear>Sword(6) — сильний напрямок.
# Sword-vs-Sword = 2 (баг 1.5, було 3 — мечник і так б'є частіше, 1 AP за удар).
WARRIOR_DAMAGE = {
    "Sword": {"Sword": 2, "Mace": 6, "Spear": 1},
    "Mace":  {"Sword": 2, "Mace": 3, "Spear": 6},
    "Spear": {"Sword": 6, "Mace": 2, "Spear": 3},
}
WARRIOR_VS_BUILDING_DAMAGE = {"Sword": 1, "Spear": 1, "Mace": 3}
WARRIOR_VS_SHIP_DAMAGE = {"Sword": 1, "Spear": 1, "Mace": 3}
WARRIOR_VS_CATAPULT_DAMAGE = {"Sword": 1, "Spear": 1, "Mace": 3}
WARRIOR_VS_WORKER_DAMAGE = 2

SHIELDS_ARROW_DAMAGE_REDUCTION = 1    # тех. Кузні: -1 шкоди мечнику від стріл (лучник/вежа)
BETTER_MACES_BONUS = 1                # тех. Кузні: +1 булаві проти будівель/катапульт/кораблів
ALEBARDS_BONUS_VS_HORSEMAN = 3        # тех. Кузні: +3 спису проти вершника

# ---------------------------------------------------------------------------
# Лучник (5.5.6)
# ---------------------------------------------------------------------------

ARCHER_HP = 3
ARCHER_ACTION_POINTS = UNIT_ACTION_POINTS
ARCHER_RANGE = 2
ARCHER_RANGE_UPGRADED = 3             # тех. "Арбалети" (Лісопилка)
ARCHER_COST = {"gold": 0, "wood": 3, "food": 3}

# Шкода лучника по типу цілі (kind юніта, або warrior_type для воїнів).
ARCHER_ATTACK_VS = {
    "Worker": 1, "Mage": 1, "Ship": 1, "Catapult": 1, "CannonBoat": 1,
    "Horseman": 2, "Sword": 2, "Spear": 2, "Mace": 2, "Archer": 2,
}
# Шкода, яку лучник ОТРИМУЄ від інших (ближній бій по лучнику).
ARCHER_DAMAGE_TAKEN = {
    "Worker": 1, "Mage": 1,
    "Sword": 3, "Mace": 3, "Spear": 3, "Horseman": 3,
}

# ---------------------------------------------------------------------------
# Вершник на коні (5.5.7)
# ---------------------------------------------------------------------------

HORSEMAN_HP = 9
HORSEMAN_COST = {"gold": 3, "wood": 0, "food": 5}
HORSEMAN_ATTACK_VS = {
    "Worker": 3, "Mage": 3, "Archer": 3, "Spear": 3, "Mace": 3, "Horseman": 3,
    "Sword": 6,
}
HORSEMAN_ATTACK_VS_STRUCTURE = 1      # будівлі, кораблі, катапульти
HORSEMAN_DAMAGE_TAKEN = {
    "Sword": 3, "Horseman": 3, "Spear": 6, "Mace": 4, "Archer": 2,
    "Mage": 1, "Worker": 1,
}

# ---------------------------------------------------------------------------
# Катапульта (5.5.2) — потребує технологію Heavy Artillery (Кузня)
# ---------------------------------------------------------------------------

CATAPULT_HP = 6
CATAPULT_MIN_RANGE = 2                # не може по сусідній клітинці
CATAPULT_MAX_RANGE = 3
CATAPULT_ATTACK = 6
CATAPULT_COST = {"gold": 5, "wood": 5, "food": 0}

# ---------------------------------------------------------------------------
# Маг та слизень (5.5.4)
# ---------------------------------------------------------------------------

MAGE_HP = 2
MAGE_ATTACK_VS_UNIT = 1
MAGE_HIRE_COST = {"gold": 8, "wood": 0, "food": 0}

SLIME_HP = 1
SLIME_ATTACK = 1
SLIME_ACTION_POINTS = 1

SPELL_AP_COST = ACTION_COST_SPELL
MAGIC_SHIELD_DAMAGE_REDUCTION = 1
TELEPORT_DISTANCE = 5
THUNDER_DAMAGE_VS_SHIP = 6

# ключ: (shortcut, ціна золота за використання, дальність, ціна технології
# {ресурс: сума} або None якщо доступно одразу безкоштовно як технологія)
SPELLS = {
    "Heal":            {"shortcut": "h", "use_cost": {"gold": 0}, "range": 2, "tech_cost": None},
    "Freeze":          {"shortcut": "f", "use_cost": {"gold": 1}, "range": 3, "tech_cost": {"gold": 5, "wood": 0, "food": 0}},
    "MagicShield":     {"shortcut": "s", "use_cost": {"gold": 1}, "range": 2, "tech_cost": {"gold": 5, "wood": 0, "food": 0}},
    "YouShallNotPass": {"shortcut": "y", "use_cost": {"gold": 1}, "range": 3, "tech_cost": {"gold": 5, "wood": 0, "food": 0}},
    "Teleport":        {"shortcut": "t", "use_cost": {"gold": 1}, "range": 2, "tech_cost": {"gold": 8, "wood": 0, "food": 0}},
    "SummonSlime":     {"shortcut": "i", "use_cost": {"gold": 0}, "range": 1, "tech_cost": {"gold": 3, "wood": 0, "food": 0}},
    "Thunder":         {"shortcut": "g", "use_cost": {"gold": 1}, "range": 4, "tech_cost": {"gold": 8, "wood": 0, "food": 0}},
}
# Заклинання, доступні ЛИШЕ дослідивши відповідну технологію в Школі магії
# (усі, крім Heal — воно безкоштовне і доступне одразу).
SPELLS_REQUIRING_TECH = [name for name in SPELLS if SPELLS[name]["tech_cost"] is not None]

# ---------------------------------------------------------------------------
# Корабель / Корабель з гарматою (5.3)
# ---------------------------------------------------------------------------

SHIP_HP = 12                          # обидва типи кораблів
SHIP_MOVE_RANGE = 3
SHIP_CAPACITY = 3
SHIP_BOARD_HOTKEYS = ["q", "w", "e"]  # по одній клавіші на місце
SHIP_COST = {"gold": 3, "wood": 5, "food": 3}

CANNON_BOAT_MOVE_RANGE = 2
CANNON_BOAT_MIN_RANGE = 1             # на відміну від катапульти — стріляє й по сусідніх
CANNON_BOAT_MAX_RANGE = 3
CANNON_BOAT_ATTACK = 6
CANNON_BOAT_COST = {"gold": SHIP_COST["gold"] + 3, "wood": SHIP_COST["wood"], "food": SHIP_COST["food"]}

PORT_HP = 8
PORT_COST = {"gold": 3, "wood": 8, "food": 3}
PORT_TRADE_GIVE_AMOUNT = 3
PORT_TRADE_GET_AMOUNT = 1
PORT_TRADE_HOTKEYS = ["1", "2", "3", "4", "5", "6"]
# 6 впорядкованих пар (віддаю -> отримую) між 3 ресурсами.
PORT_TRADE_PAIRS = [
    ("gold", "wood"), ("gold", "food"),
    ("wood", "gold"), ("wood", "food"),
    ("food", "gold"), ("food", "wood"),
]

# ---------------------------------------------------------------------------
# Замок / Дім (House) та Стайня (Horse)
# ---------------------------------------------------------------------------

CASTLE_HP = 25
CASTLE_HOUSE_BONUS = 5

HOUSE_HP = 5
HOUSE_COST = {"gold": 0, "wood": 3, "food": 1}
HOUSE_BONUS = 5

HORSE_STABLE_HP = 8
HORSE_STABLE_COST = {"gold": 0, "wood": 5, "food": 8}
HORSE_STABLE_REQUIRES_TECH = "Horses"     # тех. Ферми
HORSE_BONUS = 3
FASTER_HORSES_COST = {"gold": 4, "wood": 0, "food": 4}  # TODO: ціна не вказана в ТЗ, орієнтовний плейсхолдер

# ---------------------------------------------------------------------------
# Ресурсні будівлі (Лісопильня / Ферма / Шахта) + прокачка (5.2)
# ---------------------------------------------------------------------------

RESOURCE_BUILDING_HP = 7
RESOURCE_BUILDING_CAPACITY = 3
RESOURCE_BUILDING_CAPACITY_UPGRADED = 5
RESOURCE_PER_WORKER = 1

LUMBER_MILL_COST = {"gold": 3, "wood": 0, "food": 0}
MILL_COST = {"gold": 0, "wood": 3, "food": 0}         # Farm (4.2 — перейменована з Mill)
MINE_COST = {"gold": 0, "wood": 3, "food": 3}

RESOURCE_BUILDING_TILE_TO_KIND = {
    "forest": "LumberMill",
    "wheat": "Mill",
    "mountain": "Mine",
}
RESOURCE_BUILDING_KIND_TO_RESOURCE = {
    "LumberMill": "wood",
    "Mill": "food",
    "Mine": "gold",
}

BUILDING_UPGRADE_COST = {
    "Mill": {"gold": 5, "wood": 5, "food": 0},
    "LumberMill": {"gold": 5, "wood": 0, "food": 5},
    "Mine": {"gold": 0, "wood": 5, "food": 5},
}
BUILDING_UPGRADE_CANCEL_REFUND = 1        # повертає 1 з кожного витраченого ресурсу
BUILDING_UPGRADE_TARGET_PROGRESS = 6      # шкала будування має досягти >= 6
UPGRADED_RESOURCE_BUILDING_HP_BONUS = 3

# ---------------------------------------------------------------------------
# Дерево технологій ресурсних будівель (5.2.1)
# ---------------------------------------------------------------------------

FARM_TECHS = {
    "Bread": {"gold": 0, "wood": 0, "food": 8},
    "Horses": {"gold": 3, "wood": 0, "food": 8},
}
LUMBERMILL_TECHS = {
    "Bow": {"gold": 0, "wood": 8, "food": 0},
    "Crossbow": {"gold": 5, "wood": 10, "food": 0},   # потребує Bow
}
MINE_TECHS = {
    "BetterRepair": {"gold": 5, "wood": 5, "food": 0},
    "ArmoredTowers": {"gold": 7, "wood": 5, "food": 0},
}
RESOURCE_BUILDING_TECHS = {
    "Mill": FARM_TECHS,
    "LumberMill": LUMBERMILL_TECHS,
    "Mine": MINE_TECHS,
}
TECH_PREREQUISITE = {"Crossbow": "Bow"}
ARMORED_TOWERS_BONUS_HP = 3

# ---------------------------------------------------------------------------
# Казарма (5.5.5 rework) / Кузня (5.5.1) / Школа магії (5.5.4)
# ---------------------------------------------------------------------------

BARRACKS_HP = 8
BARRACKS_COST = {"gold": 5, "wood": 3, "food": 3}

SMITHY_HP = 8
SMITHY_COST = {"gold": 8, "wood": 3, "food": 0}
SMITHY_TECHS = {
    "Shields": {"gold": 8, "wood": 0, "food": 0},
    "BetterMaces": {"gold": 7, "wood": 0, "food": 0},
    "Alebards": {"gold": 3, "wood": 7, "food": 0},
    "HeavyArtillery": {"gold": 8, "wood": 5, "food": 0},
}
SMITHY_TECH_HOTKEYS = {"Shields": "s", "BetterMaces": "d", "Alebards": "a", "HeavyArtillery": "c"}

MAGIC_SCHOOL_HP = 12
MAGIC_SCHOOL_COST = {"gold": 10, "wood": 7, "food": 0}

# ---------------------------------------------------------------------------
# Вежа (5.4 rework — без гарнізону, прокачується до одного з 3 типів)
# ---------------------------------------------------------------------------

TOWER_HP = 10
TOWER_COST = {"gold": 2, "wood": 5, "food": 0}   # базова, ще нічого не вміє

TOWER_UPGRADE_KINDS = ("ArcherTower", "MageTower", "CannonTower")
TOWER_UPGRADE_COST = {
    "ArcherTower": {"gold": 0, "wood": 3, "food": 3},
    "MageTower": {"gold": 3, "wood": 0, "food": 3},
    "CannonTower": {"gold": 3, "wood": 3, "food": 0},
}
TOWER_UPGRADE_HOTKEYS = {"ArcherTower": "s", "MageTower": "m", "CannonTower": "c"}
# Що потрібно, щоб прокачка стала доступною: назва технології АБО
# спеціальний рядок "MagicSchoolBuilt" (перевіряється окремо в game_logic).
TOWER_UPGRADE_REQUIRES = {
    "ArcherTower": "Bow",
    "MageTower": "MagicSchoolBuilt",
    "CannonTower": "HeavyArtillery",
}

ARCHER_TOWER_RANGE = 2
ARCHER_TOWER_RANGE_UPGRADED = 3
MAGE_TOWER_RANGE = 3
CANNON_TOWER_RANGE = 3
CANNON_TOWER_MIN_RANGE = 1            # на відміну від катапульти — б'є і по сусідніх
CANNON_TOWER_ATTACK = 6

BRIDGE_COST = {"gold": 0, "wood": 5, "food": 0}

UNDER_CONSTRUCTION_HP = 2

# ---------------------------------------------------------------------------
# Крадіжка ресурсів (5.1)
# ---------------------------------------------------------------------------

STEAL_AMOUNT = 1
STEAL_RESOURCE_BY_BUILDING = {"Mill": "food", "LumberMill": "wood", "Mine": "gold"}
STEALABLE_BUILDING_KINDS = ("Mill", "LumberMill", "Mine", "Castle")

# ---------------------------------------------------------------------------
# Зведені таблиці для game_logic.py / ui_game.py
# ---------------------------------------------------------------------------

BUILDING_HP = {
    "Castle": CASTLE_HP,
    "House": HOUSE_HP,
    "LumberMill": RESOURCE_BUILDING_HP,
    "Mill": RESOURCE_BUILDING_HP,
    "Mine": RESOURCE_BUILDING_HP,
    "Barracks": BARRACKS_HP,
    "Tower": TOWER_HP,
    "Port": PORT_HP,
    "Bridge": 1,
    "Smithy": SMITHY_HP,
    "HorseStable": HORSE_STABLE_HP,
    "MagicSchool": MAGIC_SCHOOL_HP,
    "UnderConstruction": UNDER_CONSTRUCTION_HP,
}

BUILDING_COSTS = {
    "House": HOUSE_COST,
    "LumberMill": LUMBER_MILL_COST,
    "Mill": MILL_COST,
    "Mine": MINE_COST,
    "Barracks": BARRACKS_COST,
    "Tower": TOWER_COST,
    "Bridge": BRIDGE_COST,
    "Port": PORT_COST,
    "Smithy": SMITHY_COST,
    "HorseStable": HORSE_STABLE_COST,
    "MagicSchool": MAGIC_SCHOOL_COST,
}

# Тайл, необхідний для будівництва. None = будь-який непрохідний-по-воді тайл.
# "water" = спеціальний випадок (Bridge будується саме на воді).
BUILDING_REQUIRED_TILE = {
    "House": "grass",
    "LumberMill": "forest",
    "Mill": "wheat",
    "Mine": "mountain",
    "Barracks": None,
    "Tower": None,
    "Port": "grass",
    "Bridge": "water",
    "Smithy": None,
    "HorseStable": None,
    "MagicSchool": None,
}

# Порядок кнопок будівництва в меню робітника.
BUILDABLE_KINDS = [
    "House", "LumberMill", "Mill", "Mine", "Barracks", "Tower", "Port", "Bridge",
    "Smithy", "HorseStable", "MagicSchool",
]

HOUSE_BONUS_BY_KIND = {
    "Castle": CASTLE_HOUSE_BONUS,
    "House": HOUSE_BONUS,
}
HORSE_BONUS_BY_KIND = {
    "HorseStable": HORSE_BONUS,
}

# ---------------------------------------------------------------------------
# Гарячі клавіші
# ---------------------------------------------------------------------------

KEY_TO_BUILD_KIND = {
    "h": "House", "t": "Tower", "l": "LumberMill", "m": "Mine",
    "f": "Mill", "b": "Barracks", "n": "Bridge", "p": "Port",
    "s": "Smithy", "v": "HorseStable", "g": "MagicSchool",
}
KEY_TO_WARRIOR_TYPE = {"s": "Sword", "a": "Spear", "d": "Mace"}
KEY_TO_BARRACKS_UNIT = {"s": "Sword", "a": "Spear", "d": "Mace", "w": "Archer", "q": "Horseman"}
