"""
Little Kingdoms — моделі гравців, юнітів та будівель (Beta).

Система очок дії (action_points): Worker/Warrior/Archer/Mage/Slime мають
config.UNIT_ACTION_POINTS (2), Horseman — свій, більший пул
(config.HORSEMAN_ACTION_POINTS), Catapult/CannonBoat — лише 1 очко
(похід АБО атака). Ship лишається на tired-прапорці (одна дія/хід).

Статус-ефекти мага (frozen/shielded) зберігаються прямо на Unit, бо
можуть торкнутися будь-якого юніта (біологічного чи механічного,
включно з кораблями й катапультами) — деталі застосування в game_logic.py.

Player.researched_techs — глобальний набір назв досліджених технологій
(вони діють одразу на все господарство гравця, на відміну від прокачки
конкретної ресурсної будівлі, яка стосується лише її самої).
"""

import config


class Player:
    def __init__(self, player_id, color, is_bot):
        self.id = player_id
        self.color = color
        self.is_bot = is_bot
        self.resources = dict(config.STARTING_RESOURCES)
        self.alive = True
        self.researched_techs = set()

    @property
    def type(self):
        return "Bot" if self.is_bot else "Human"

    def can_afford(self, cost):
        return all(self.resources.get(res, 0) >= amount for res, amount in cost.items())

    def pay(self, cost):
        for res, amount in cost.items():
            self.resources[res] = self.resources.get(res, 0) - amount

    def add_resources(self, gains):
        for res, amount in gains.items():
            self.resources[res] = self.resources.get(res, 0) + amount

    def has_tech(self, tech_name):
        return tech_name in self.researched_techs


class Entity:
    """Базовий клас для всього, що займає тайл: юніти й будівлі."""

    def __init__(self, entity_id, owner_id, row, col, kind, hp, max_hp):
        self.id = entity_id
        self.owner_id = owner_id
        self.row = row
        self.col = col
        self.kind = kind
        self.hp = hp
        self.max_hp = max_hp

    def is_alive(self):
        return self.hp > 0

    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)
        return self.hp <= 0

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)


# ---------------------------------------------------------------------------
# Юніти
# ---------------------------------------------------------------------------

class Unit(Entity):
    def __init__(self, entity_id, owner_id, row, col, kind, hp, max_hp):
        super().__init__(entity_id, owner_id, row, col, kind, hp, max_hp)
        self.warrior_type = None  # лише для Warrior
        self.tired = False        # використовується лише кораблем (Ship)

        # Статус-ефекти мага (5.5.4). frozen: заблокований на СВІЙ наступний
        # хід (знімається на початку наступного після того start_turn).
        # shielded: наступна отримана шкода зменшена на
        # config.MAGIC_SHIELD_DAMAGE_REDUCTION, ефект згасає на початку
        # наступного ходу власника незалежно від того, спрацював він чи ні.
        self.frozen = False
        self.shielded = False


class Worker(Unit):
    def __init__(self, entity_id, owner_id, row, col):
        super().__init__(entity_id, owner_id, row, col, "Worker", config.WORKER_HP, config.WORKER_HP)
        self.action_points = config.UNIT_ACTION_POINTS


class Warrior(Unit):
    def __init__(self, entity_id, owner_id, row, col, warrior_type, action_points=None):
        super().__init__(entity_id, owner_id, row, col, "Warrior", config.WARRIOR_HP, config.WARRIOR_HP)
        self.warrior_type = warrior_type
        # Щойно навчені воїни мають 0 очок дій цього ходу — усі сили
        # пішли на тренування (за замовчуванням, якщо не передано інше).
        self.action_points = config.UNIT_ACTION_POINTS if action_points is None else action_points


class Archer(Unit):
    """5.5.6 — тренується в Казармі (W). Дальність 2, з Арбалетами — 3."""

    def __init__(self, entity_id, owner_id, row, col, action_points=None):
        super().__init__(entity_id, owner_id, row, col, "Archer", config.ARCHER_HP, config.ARCHER_HP)
        self.action_points = config.ARCHER_ACTION_POINTS if action_points is None else action_points


class Horseman(Unit):
    """5.5.7 — тренується в Казармі (Q). Займає і House, і Horse у Стайні."""

    def __init__(self, entity_id, owner_id, row, col, action_points=None):
        super().__init__(entity_id, owner_id, row, col, "Horseman", config.HORSEMAN_HP, config.HORSEMAN_HP)
        base_ap = config.HORSEMAN_ACTION_POINTS
        self.action_points = base_ap if action_points is None else action_points


class Mage(Unit):
    """5.5.4 — навчається в Школі магії. Слабкий у бою, сильний заклинаннями."""

    def __init__(self, entity_id, owner_id, row, col, action_points=None):
        super().__init__(entity_id, owner_id, row, col, "Mage", config.MAGE_HP, config.MAGE_HP)
        self.action_points = config.UNIT_ACTION_POINTS if action_points is None else action_points


class Slime(Unit):
    """Викликається закляттям SummonSlime. 1 HP, 1 атака, 1 очко дії."""

    def __init__(self, entity_id, owner_id, row, col):
        super().__init__(entity_id, owner_id, row, col, "Slime", config.SLIME_HP, config.SLIME_HP)
        self.action_points = config.SLIME_ACTION_POINTS


class Catapult(Unit):
    """5.5.2 — потребує технологію Heavy Artillery. 1 очко дії: похід АБО
    атака (дальність 2-3, не може по сусідній клітинці)."""

    def __init__(self, entity_id, owner_id, row, col, action_points=None):
        super().__init__(entity_id, owner_id, row, col, "Catapult", config.CATAPULT_HP, config.CATAPULT_HP)
        self.action_points = config.CATAPULT_ACTION_POINTS if action_points is None else action_points


class Ship(Unit):
    def __init__(self, entity_id, owner_id, row, col):
        super().__init__(entity_id, owner_id, row, col, "Ship", config.SHIP_HP, config.SHIP_HP)
        self.passengers = []  # список id юнітів на борту (макс. config.SHIP_CAPACITY)


class CannonBoat(Unit):
    """5.3 — окремий юніт (НЕ Ship): 1 очко дії, дальність ходу 2, не бере
    пасажирів, стріляє як катапульта, але може й по сусідніх клітинках."""

    def __init__(self, entity_id, owner_id, row, col, action_points=None):
        super().__init__(entity_id, owner_id, row, col, "CannonBoat", config.SHIP_HP, config.SHIP_HP)
        self.action_points = config.CANNON_BOAT_ACTION_POINTS if action_points is None else action_points


# ---------------------------------------------------------------------------
# Будівлі
# ---------------------------------------------------------------------------

class Building(Entity):
    def __init__(self, entity_id, owner_id, row, col, kind, hp, max_hp):
        super().__init__(entity_id, owner_id, row, col, kind, hp, max_hp)
        # Спільне поле для будь-якої будівлі, що вміє досліджувати технології
        # (ResourceBuilding/Smithy/HorseStable/MagicSchool). None = нічого
        # не замовлено. Технологія завершується на початку наступного ходу.
        self.researching_tech = None


class Castle(Building):
    def __init__(self, entity_id, owner_id, row, col):
        super().__init__(entity_id, owner_id, row, col, "Castle", config.CASTLE_HP, config.CASTLE_HP)


class House(Building):
    def __init__(self, entity_id, owner_id, row, col):
        super().__init__(entity_id, owner_id, row, col, "House", config.HOUSE_HP, config.HOUSE_HP)


class ResourceBuilding(Building):
    """LumberMill / Mill / Mine — вміщує робітників, що добувають ресурс.

    Прокачка (5.2): upgrading=True під час будівництва прокачки (тоді
    ресурс НЕ виробляється), upgrade_progress росте на кінець кожного
    ходу на кількість робітників усередині, і коли досягає
    config.BUILDING_UPGRADE_TARGET_PROGRESS — будівля стає upgraded=True
    (5 місць замість 3, +3 максимального здоров'я, повне зцілення).
    """

    def __init__(self, entity_id, owner_id, row, col, kind):
        super().__init__(entity_id, owner_id, row, col, kind,
                          config.RESOURCE_BUILDING_HP, config.RESOURCE_BUILDING_HP)
        self.workers_inside = []  # список id робітників
        self.upgrading = False
        self.upgrade_progress = 0
        self.upgraded = False

    @property
    def resource_type(self):
        return config.RESOURCE_BUILDING_KIND_TO_RESOURCE[self.kind]

    @property
    def capacity(self):
        return config.RESOURCE_BUILDING_CAPACITY_UPGRADED if self.upgraded else config.RESOURCE_BUILDING_CAPACITY

    def has_space(self):
        return len(self.workers_inside) < self.capacity


class Barracks(Building):
    def __init__(self, entity_id, owner_id, row, col):
        super().__init__(entity_id, owner_id, row, col, "Barracks", config.BARRACKS_HP, config.BARRACKS_HP)


class Smithy(Building):
    """5.5.1 — 4 технології: Shields, Better Maces, Alebards, Heavy Artillery."""

    def __init__(self, entity_id, owner_id, row, col):
        super().__init__(entity_id, owner_id, row, col, "Smithy", config.SMITHY_HP, config.SMITHY_HP)


class HorseStable(Building):
    """5.5.3 — потребує технологію "Horses" (Ферма). Дає ресурс Horse
    (за аналогією з House), +config.HORSE_BONUS місць за будівлю."""

    def __init__(self, entity_id, owner_id, row, col):
        super().__init__(entity_id, owner_id, row, col, "HorseStable",
                          config.HORSE_STABLE_HP, config.HORSE_STABLE_HP)


class MagicSchool(Building):
    """5.5.4 — тут наймають Мага (як воїна в Бараках) і досліджують
    7 заклинань (див. config.SPELLS)."""

    def __init__(self, entity_id, owner_id, row, col):
        super().__init__(entity_id, owner_id, row, col, "MagicSchool",
                          config.MAGIC_SCHOOL_HP, config.MAGIC_SCHOOL_HP)


class Tower(Building):
    """5.4 rework — БЕЗ гарнізону. Базова вежа нічого не вміє, доки її не
    прокачають до одного з 3 типів (tower_type). Прокачка — окремий
    "будується" стан (upgrading_to), що завершується на початку
    наступного ходу власника, так само як зведення нової будівлі."""

    def __init__(self, entity_id, owner_id, row, col):
        super().__init__(entity_id, owner_id, row, col, "Tower", config.TOWER_HP, config.TOWER_HP)
        self.tower_type = None       # None | "ArcherTower" | "MageTower" | "CannonTower"
        self.upgrading_to = None     # тип прокачки, що будується цього ходу
        self.has_fired_this_turn = False


class Port(Building):
    def __init__(self, entity_id, owner_id, row, col):
        super().__init__(entity_id, owner_id, row, col, "Port", config.PORT_HP, config.PORT_HP)


class Bridge(Building):
    """Не має бою — лише перетворює тайл води на прохідний."""

    def __init__(self, entity_id, owner_id, row, col):
        super().__init__(entity_id, owner_id, row, col, "Bridge", 1, 1)


class UnderConstruction(Building):
    """Тимчасова будівля: на початку наступного ходу власника перетворюється
    на target_kind. Юніт, що після завершення опиниться на цій клітинці
    (якщо може туди зайти), автоматично сяде всередину безкоштовно.

    Використовується лише для ЗВЕДЕННЯ нових будівель — прокачка вежі має
    власний механізм (Tower.upgrading_to), бо на відміну від нової будівлі
    прокачка повинна зберегти ідентичність/здоров'я вже існуючої вежі."""

    def __init__(self, entity_id, owner_id, row, col, target_kind):
        super().__init__(entity_id, owner_id, row, col, "UnderConstruction",
                          config.UNDER_CONSTRUCTION_HP, config.UNDER_CONSTRUCTION_HP)
        self.target_kind = target_kind
