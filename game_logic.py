"""
Little Kingdoms — ігрова логіка (Beta).

GameState зберігає весь стан гри (сітку тайлів, гравців, юніти, будівлі)
і надає методи для всіх дій. Модуль не залежить від tkinter — ui_game.py
лише читає стан і викликає ці методи.

Система очок дії (AP): Worker/Warrior/Archer/Mage/Slime мають
config.UNIT_ACTION_POINTS (2) очок на хід, Horseman — свій, більший пул
(config.HORSEMAN_ACTION_POINTS, + Faster Horses тех.), Catapult/CannonBoat —
лише 1 (похід АБО атака). Дія виконується, якщо AP > 0; її вартість
віднімається і не може опуститись нижче 0. Ship лишається на прапорці
tired (одна дія/хід).

Загальний цикл ходу:
    1. GameState.end_turn() — поточний гравець отримує ресурси, прогрес
       прокачки ресурсних будівель зростає на кількість робітників у них,
       хід передається далі.
    2. GameState.start_turn(new_player) викликається автоматично:
       завершує будівництва/прокачки веж/прокачки будівель/дослідження
       технологій, знімає/накладає ефекти заморозки, скидає AP/tired,
       вежі стріляють.

Нове в Beta (стисло — детальніше в config.py):
  - Крадіжка ресурсів робітником (замість атаки будівель).
  - Прокачка ресурсних будівель + дерево технологій (Ферма/Лісопилка/
    Шахта/Кузня/Стайня/Школа магії), технології діють глобально на
    гравця, прокачка стосується лише конкретної будівлі.
  - Нові юніти: Archer, Horseman, Catapult, Mage, Slime, CannonBoat.
  - Вежа без гарнізону: прокачується до Archer/Mage/CannonTower.
  - Порт як ринок (обмін ресурсів) + виробництво CannonBoat.
  - 7 заклинань мага (config.SPELLS).

ВІДОМІ СПРОЩЕННЯ / TODO (не описані явно в ТЗ):
  - Ціна технології FasterHorses (Стайня) — орієнтовний плейсхолдер,
    див. config.py.
  - Генерація річок (баг 1.8) НЕ виправлена тут — це world_gen.py,
    торкнемось окремим проходом по цьому файлу.
  - repair_target тепер повертає target_kind "unit" замість "ship" —
    зміна публічного API, ui_game.py доведеться підлаштувати.
"""

import random

import config
from world_gen import TILE_WATER
from models import (
    Player, Worker, Warrior, Archer, Horseman, Mage, Slime, Catapult,
    Ship, CannonBoat,
    Castle, House, ResourceBuilding, Barracks, Smithy, HorseStable,
    MagicSchool, Tower, Port, Bridge, UnderConstruction,
)

_BUILDING_FACTORY = {
    "House": lambda eid, oid, r, c: House(eid, oid, r, c),
    "LumberMill": lambda eid, oid, r, c: ResourceBuilding(eid, oid, r, c, "LumberMill"),
    "Mill": lambda eid, oid, r, c: ResourceBuilding(eid, oid, r, c, "Mill"),
    "Mine": lambda eid, oid, r, c: ResourceBuilding(eid, oid, r, c, "Mine"),
    "Barracks": lambda eid, oid, r, c: Barracks(eid, oid, r, c),
    "Tower": lambda eid, oid, r, c: Tower(eid, oid, r, c),
    "Port": lambda eid, oid, r, c: Port(eid, oid, r, c),
    "Bridge": lambda eid, oid, r, c: Bridge(eid, oid, r, c),
    "Smithy": lambda eid, oid, r, c: Smithy(eid, oid, r, c),
    "HorseStable": lambda eid, oid, r, c: HorseStable(eid, oid, r, c),
    "MagicSchool": lambda eid, oid, r, c: MagicSchool(eid, oid, r, c),
}

# Юніти, що б'ються виключно через ranged_attack (не через сусідню interact-атаку).
_RANGED_ONLY_ATTACKERS = ("Archer", "Catapult")
# Юніти, що можуть атакувати ворожі будівлі впритул (не Worker — той краде,
# не Archer/Catapult/Mage/Slime — ті або дальнобійні, або по будівлях не б'ють).
_MELEE_BUILDING_ATTACKERS = ("Warrior", "Horseman")
# "Кораблеподібні" юніти — спільні для таблиць шкоди/потоплення з пасажирами.
_SHIP_LIKE_KINDS = ("Ship", "CannonBoat")


class GameState:
    def __init__(self, grid, players_config):
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0]) if self.rows else 0

        self.player_order = [p["id"] for p in players_config]
        self.players = {p["id"]: Player(p["id"], p["color"], p["type"] == "Bot") for p in players_config}

        self.buildings = {}
        self.building_pos = {}
        self.units = {}
        self.unit_pos = {}
        self._next_id = 1

        self.current_index = 0
        self.game_over = False
        self.winner_id = None

    # ------------------------------------------------------------------
    # Базові допоміжні методи
    # ------------------------------------------------------------------
    def _new_id(self):
        new_id = self._next_id
        self._next_id += 1
        return new_id

    @property
    def current_player_id(self):
        return self.player_order[self.current_index]

    def current_player(self):
        return self.players[self.current_player_id]

    def alive_player_ids(self):
        return [pid for pid in self.player_order if self.players[pid].alive]

    def _in_bounds(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.cols

    def _neighbors8(self, r, c):
        result = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if self._in_bounds(nr, nc):
                    result.append((nr, nc))
        return result

    def _is_adjacent(self, r1, c1, r2, c2):
        return (r1, c1) != (r2, c2) and max(abs(r1 - r2), abs(c1 - c2)) == 1

    def _is_passable_for_land_unit(self, r, c):
        if self.grid[r][c] != TILE_WATER:
            return True
        bridge_id = self.building_pos.get((r, c))
        return bridge_id is not None and self.buildings[bridge_id].kind == "Bridge"

    def _is_free_for_land_placement(self, r, c, owner_id):
        """Прохідно, порожньо від юнітів і не є ЧУЖОЮ будівлею — використовується
        для спавну/виведення/виходу/телепорту, щоб юніт не опинявся на ворожій території."""
        if not self._is_passable_for_land_unit(r, c) or (r, c) in self.unit_pos:
            return False
        b_id = self.building_pos.get((r, c))
        if b_id is not None and self.buildings[b_id].owner_id != owner_id:
            return False
        return True

    # ------------------------------------------------------------------
    # Очки дії (AP) — уніфікована обробка AP-юнітів і Ship (tired)
    # ------------------------------------------------------------------
    def _is_exhausted(self, unit):
        if unit.kind == "Ship":
            return unit.tired
        return unit.action_points <= 0

    def _spend_ap(self, unit, cost):
        if unit.kind == "Ship":
            unit.tired = True
        else:
            unit.action_points = max(0, unit.action_points - cost)

    def _exhaust_fully(self, unit):
        """Використовується для дій, які завжди виснажують юніта повністю
        (наприклад, вихід з корабля/будівлі, заморозка)."""
        if unit.kind == "Ship":
            unit.tired = True
        else:
            unit.action_points = 0

    def _worker_action_cost(self, owner_id, base_cost):
        """Тех. "Хліб" (Ферма): будівництво/ремонт/крадіжка коштують 1 AP
        замість звичайних 2."""
        return config.BREAD_ACTION_COST if self.players[owner_id].has_tech("Bread") else base_cost

    # ------------------------------------------------------------------
    # Ініціалізація світу
    # ------------------------------------------------------------------
    def place_castle(self, owner_id, row, col):
        castle_id = self._new_id()
        castle = Castle(castle_id, owner_id, row, col)
        self.buildings[castle_id] = castle
        self.building_pos[(row, col)] = castle_id
        return castle

    def begin_game(self):
        self.start_turn(self.current_player_id)

    # ------------------------------------------------------------------
    # House / Horse used-max
    # ------------------------------------------------------------------
    def house_limit(self, owner_id):
        return sum(
            config.HOUSE_BONUS_BY_KIND.get(b.kind, 0)
            for b in self.buildings.values() if b.owner_id == owner_id
        )

    def house_used(self, owner_id):
        # Усі юніти (Worker, Warrior, Archer, Horseman, Mage, Slime, Ship,
        # CannonBoat, Catapult) займають 1 House. Вершник ДОДАТКОВО займає Horse.
        return sum(1 for u in self.units.values() if u.owner_id == owner_id)

    def horse_limit(self, owner_id):
        return sum(
            config.HORSE_BONUS_BY_KIND.get(b.kind, 0)
            for b in self.buildings.values() if b.owner_id == owner_id
        )

    def horse_used(self, owner_id):
        return sum(1 for u in self.units.values() if u.owner_id == owner_id and u.kind == "Horseman")

    # ------------------------------------------------------------------
    # Ресурси / хід
    # ------------------------------------------------------------------
    def preview_next_gain(self, owner_id):
        gains = {"gold": 0, "wood": 0, "food": 0}
        for b in self.buildings.values():
            if (b.owner_id == owner_id and isinstance(b, ResourceBuilding) and not b.upgrading):
                gains[b.resource_type] += len(b.workers_inside) * config.RESOURCE_PER_WORKER
        return gains

    def end_turn(self):
        if self.game_over:
            return
        pid = self.current_player_id
        gains = self.preview_next_gain(pid)
        self.players[pid].add_resources(gains)
        self._advance_building_upgrades(pid)

        for _ in range(len(self.player_order)):
            self.current_index = (self.current_index + 1) % len(self.player_order)
            if self.players[self.current_player_id].alive:
                break

        self.start_turn(self.current_player_id)

    def _advance_building_upgrades(self, owner_id):
        """5.2 — шкала прокачки заповнюється на кінець ходу на кількість
        робітників, що були в будівлі станом на цей момент."""
        for b in self.buildings.values():
            if b.owner_id == owner_id and isinstance(b, ResourceBuilding) and b.upgrading:
                b.upgrade_progress += len(b.workers_inside)

    def start_turn(self, owner_id):
        self._complete_constructions(owner_id)
        self._complete_tower_upgrades(owner_id)
        self._complete_resource_upgrades(owner_id)
        self._complete_tech_research(owner_id)

        for unit in self.units.values():
            if unit.owner_id != owner_id:
                continue

            unit.shielded = False  # ефект щита згасає на початку ходу власника
            if unit.frozen:
                # Заблокований САМЕ цей хід; лід зникає — далі знову норма.
                self._exhaust_fully(unit)
                unit.frozen = False
                continue

            if unit.kind == "Ship":
                unit.tired = False
            elif unit.kind == "Horseman":
                bonus = config.FASTER_HORSES_BONUS_AP if self.players[owner_id].has_tech("FasterHorses") else 0
                unit.action_points = config.HORSEMAN_ACTION_POINTS + bonus
            elif unit.kind == "Catapult":
                unit.action_points = config.CATAPULT_ACTION_POINTS
            elif unit.kind == "CannonBoat":
                unit.action_points = config.CANNON_BOAT_ACTION_POINTS
            else:
                unit.action_points = config.UNIT_ACTION_POINTS

        self._fire_towers(owner_id)

    # ------------------------------------------------------------------
    # Завершення будівництва (+ автовхід юніта, що стоїть зверху)
    # ------------------------------------------------------------------
    def _complete_constructions(self, owner_id):
        finished = [
            b for b in self.buildings.values()
            if b.owner_id == owner_id and isinstance(b, UnderConstruction)
        ]
        for uc in finished:
            factory = _BUILDING_FACTORY[uc.target_kind]
            new_building = factory(uc.id, uc.owner_id, uc.row, uc.col)
            self.buildings[uc.id] = new_building

            occupant_id = self.unit_pos.get((uc.row, uc.col))
            if occupant_id is not None:
                occupant = self.units.get(occupant_id)
                if occupant is not None and occupant.owner_id == owner_id:
                    self._auto_enter_if_possible(occupant)

    def _complete_tower_upgrades(self, owner_id):
        for b in self.buildings.values():
            if b.owner_id == owner_id and isinstance(b, Tower) and b.upgrading_to is not None:
                b.tower_type = b.upgrading_to
                b.upgrading_to = None

    def _complete_resource_upgrades(self, owner_id):
        for b in self.buildings.values():
            if (b.owner_id == owner_id and isinstance(b, ResourceBuilding) and b.upgrading
                    and b.upgrade_progress >= config.BUILDING_UPGRADE_TARGET_PROGRESS):
                b.upgrading = False
                b.upgraded = True
                b.max_hp += config.UPGRADED_RESOURCE_BUILDING_HP_BONUS
                b.hp = b.max_hp

    def _complete_tech_research(self, owner_id):
        owner = self.players[owner_id]
        for b in self.buildings.values():
            if b.owner_id == owner_id and b.researching_tech is not None:
                owner.researched_techs.add(b.researching_tech)
                b.researching_tech = None

    # ------------------------------------------------------------------
    # Автострільба веж (5.4 rework — тип визначає tower_type, не гарнізон)
    # ------------------------------------------------------------------
    def _fire_towers(self, owner_id):
        for b in self.buildings.values():
            if b.owner_id != owner_id or not isinstance(b, Tower):
                continue
            b.has_fired_this_turn = False
            if b.tower_type is None or b.upgrading_to is not None:
                continue

            if b.tower_type == "ArcherTower":
                rng = (config.ARCHER_TOWER_RANGE_UPGRADED if self.players[owner_id].has_tech("Crossbow")
                       else config.ARCHER_TOWER_RANGE)
                target = self._find_random_enemy_unit_in_range(b.row, b.col, rng, owner_id)
                if target is not None:
                    dmg = self._archer_damage_vs(target)
                    self._apply_damage_to_unit(target, dmg)
                    b.has_fired_this_turn = True

            elif b.tower_type == "MageTower":
                target = self._find_random_enemy_unit_in_range(b.row, b.col, config.MAGE_TOWER_RANGE, owner_id)
                if target is not None:
                    target.frozen = True
                    b.has_fired_this_turn = True

            elif b.tower_type == "CannonTower":
                targets = self._siege_targets_in_range(
                    b.row, b.col, config.CANNON_TOWER_MIN_RANGE, config.CANNON_TOWER_RANGE, owner_id)
                if targets:
                    kind, target = random.choice(targets)
                    self._apply_siege_damage(kind, target, config.CANNON_TOWER_ATTACK)
                    b.has_fired_this_turn = True

    def _find_random_enemy_unit_in_range(self, r, c, rng, owner_id):
        candidates = [
            u for u in self.units.values()
            if u.owner_id != owner_id and self.unit_pos.get((u.row, u.col)) == u.id
            and max(abs(u.row - r), abs(u.col - c)) <= rng
        ]
        return random.choice(candidates) if candidates else None

    def _siege_targets_in_range(self, r, c, min_rng, max_rng, owner_id):
        """Цілі для катапульти/гарматного човна/Cannon Tower: ворожі
        кораблі/катапульти/гарматні човни та ВОРОЖІ БУДІВЛІ в кільці
        [min_rng, max_rng]. Повертає список ("unit"|"building", obj)."""
        targets = []
        for u in self.units.values():
            if (u.owner_id != owner_id and u.kind in ("Ship", "CannonBoat", "Catapult")
                    and self.unit_pos.get((u.row, u.col)) == u.id):
                dist = max(abs(u.row - r), abs(u.col - c))
                if min_rng <= dist <= max_rng:
                    targets.append(("unit", u))
        for b in self.buildings.values():
            if b.owner_id != owner_id and b.kind != "Bridge" and not isinstance(b, UnderConstruction):
                dist = max(abs(b.row - r), abs(b.col - c))
                if min_rng <= dist <= max_rng:
                    targets.append(("building", b))
        return targets

    def _apply_siege_damage(self, target_kind, target, dmg):
        if target_kind == "unit":
            self._apply_damage_to_unit(target, dmg)
        else:
            died = target.take_damage(dmg)
            if died:
                self._destroy_building(target)

    def _archer_damage_vs(self, target):
        """Спільна таблиця шкоди лучника — використовується і юнітом
        Archer, і прокачаною ArcherTower."""
        key = target.warrior_type if (target.kind == "Warrior" and target.warrior_type) else target.kind
        dmg = config.ARCHER_ATTACK_VS.get(key, 1)
        if key == "Sword" and self.players[target.owner_id].has_tech("Shields"):
            dmg = max(0, dmg - config.SHIELDS_ARROW_DAMAGE_REDUCTION)
        return dmg

    def _apply_damage_to_unit(self, unit, dmg):
        if unit.shielded:
            dmg = max(0, dmg - config.MAGIC_SHIELD_DAMAGE_REDUCTION)
        died = unit.take_damage(dmg)
        if died:
            self._remove_standalone_unit(unit)
            if unit.kind in _SHIP_LIKE_KINDS:
                for passenger_id in getattr(unit, "passengers", []):
                    self.units.pop(passenger_id, None)
        return died

    # ------------------------------------------------------------------
    # Автовхід у ресурсну будівлю (безкоштовно) — спавн/виведення/добудова під собою
    # (Вежі більше НЕ мають гарнізону — 5.4 rework.)
    # ------------------------------------------------------------------
    def get_standing_enterable_building(self, unit_id):
        unit = self.units.get(unit_id)
        if unit is None or self.unit_pos.get((unit.row, unit.col)) != unit.id:
            return None
        b_id = self.building_pos.get((unit.row, unit.col))
        if b_id is None:
            return None
        building = self.buildings[b_id]
        if building.owner_id != unit.owner_id:
            return None
        if (isinstance(building, ResourceBuilding) and unit.kind == "Worker"
                and building.has_space() and not building.upgrading):
            return b_id
        return None

    def _auto_enter_if_possible(self, unit):
        b_id = self.get_standing_enterable_building(unit.id)
        if b_id is None:
            return
        self._enter_resource_building(unit, self.buildings[b_id], spend_ap=False)

    def enter_building_free(self, unit_id):
        """Кнопка 'Go inside' — безкоштовний (0 AP) вхід, якщо юніт уже
        стоїть на будівлі, у яку не зайшов автоматично."""
        b_id = self.get_standing_enterable_building(unit_id)
        if b_id is None:
            return {"result": "blocked"}
        unit = self.units[unit_id]
        self._enter_resource_building(unit, self.buildings[b_id], spend_ap=False)
        return {"result": "entered_free"}

    # ------------------------------------------------------------------
    # Найм робітника (Замок / Дім)
    # ------------------------------------------------------------------
    def get_hire_spawn_tiles(self, building_id):
        building = self.buildings[building_id]
        return [
            (r, c) for r, c in self._neighbors8(building.row, building.col)
            if self._is_free_for_land_placement(r, c, building.owner_id)
        ]

    def _training_building_choice(self, row, col):
        """Якщо (row, col) — своя Казарма чи Школа магії, повертає відповідний
        результат вибору юніта; інакше None. Спільне для hire_worker/
        withdraw_worker/disembark — щоб новоприбулий робітник міг одразу
        отримати вибір навчання, якщо приземлився саме на цю будівлю."""
        b_id = self.building_pos.get((row, col))
        if b_id is None:
            return None
        kind = self.buildings[b_id].kind
        if kind == "Barracks":
            return "barracks_choice"
        if kind == "MagicSchool":
            return "magic_school_choice"
        return None

    def hire_worker(self, building_id, row, col):
        building = self.buildings[building_id]
        owner = self.players[building.owner_id]

        if self.house_used(building.owner_id) + 1 > self.house_limit(building.owner_id):
            return {"result": "blocked", "reason": "house_full"}
        if not owner.can_afford(config.WORKER_HIRE_COST):
            return {"result": "blocked", "reason": "cant_afford"}
        if (row, col) not in self.get_hire_spawn_tiles(building_id):
            return {"result": "blocked", "reason": "invalid_tile"}

        owner.pay(config.WORKER_HIRE_COST)
        worker = Worker(self._new_id(), building.owner_id, row, col)
        self.units[worker.id] = worker
        self.unit_pos[(row, col)] = worker.id

        choice = self._training_building_choice(row, col)
        if choice is not None:
            return {"result": choice, "worker_id": worker.id}

        self._auto_enter_if_possible(worker)
        return {"result": "hired", "unit_id": worker.id}

    # ------------------------------------------------------------------
    # Ремонт (будівлі, кораблі, гарматні човни, катапульти — 1.7)
    # ------------------------------------------------------------------
    def get_repairable_targets(self, worker_id):
        """Повертає список ("building"|"unit", entity_id)."""
        worker = self.units[worker_id]
        targets = []
        for pos in [(worker.row, worker.col)] + self._neighbors8(worker.row, worker.col):
            b_id = self.building_pos.get(pos)
            if b_id is not None:
                b = self.buildings[b_id]
                if b.owner_id == worker.owner_id and b.hp < b.max_hp and not isinstance(b, UnderConstruction):
                    targets.append(("building", b.id))
            u_id = self.unit_pos.get(pos)
            if u_id is not None:
                u = self.units[u_id]
                if u.kind in ("Ship", "CannonBoat", "Catapult") and u.owner_id == worker.owner_id and u.hp < u.max_hp:
                    targets.append(("unit", u.id))
        return targets

    def repair_target(self, worker_id, target_kind, target_id):
        worker = self.units[worker_id]
        owner = self.players[worker.owner_id]

        if self._is_exhausted(worker):
            return {"result": "blocked", "reason": "exhausted"}
        if (target_kind, target_id) not in self.get_repairable_targets(worker_id):
            return {"result": "blocked", "reason": "invalid_target"}
        if not owner.can_afford(config.WORKER_REPAIR_COST):
            return {"result": "blocked", "reason": "cant_afford"}

        owner.pay(config.WORKER_REPAIR_COST)
        entity = self.buildings[target_id] if target_kind == "building" else self.units[target_id]
        amount = config.WORKER_REPAIR_AMOUNT_UPGRADED if owner.has_tech("BetterRepair") else config.WORKER_REPAIR_AMOUNT
        entity.heal(amount)
        self._spend_ap(worker, self._worker_action_cost(worker.owner_id, config.ACTION_COST_REPAIR))
        return {"result": "repaired"}

    # ------------------------------------------------------------------
    # Крадіжка ресурсів (5.1) — замість атаки будівель робітником
    # ------------------------------------------------------------------
    def get_stealable_targets(self, worker_id):
        worker = self.units[worker_id]
        targets = []
        for r, c in self._neighbors8(worker.row, worker.col):
            b_id = self.building_pos.get((r, c))
            if b_id is None:
                continue
            b = self.buildings[b_id]
            if (b.owner_id != worker.owner_id and b.kind in config.STEALABLE_BUILDING_KINDS
                    and not isinstance(b, UnderConstruction)):
                targets.append(b.id)
        return targets

    def steal_resources(self, worker_id, building_id):
        worker = self.units[worker_id]
        owner = self.players[worker.owner_id]

        if self._is_exhausted(worker):
            return {"result": "blocked", "reason": "exhausted"}
        if building_id not in self.get_stealable_targets(worker_id):
            return {"result": "blocked", "reason": "invalid_target"}

        building = self.buildings[building_id]
        victim = self.players[building.owner_id]
        if building.kind == "Castle":
            resource = random.choice(["gold", "wood", "food"])
        else:
            resource = config.STEAL_RESOURCE_BY_BUILDING[building.kind]

        amount = min(config.STEAL_AMOUNT, victim.resources.get(resource, 0))
        if amount > 0:
            victim.resources[resource] -= amount
            owner.add_resources({resource: amount})

        self._spend_ap(worker, self._worker_action_cost(worker.owner_id, config.ACTION_COST_STEAL))
        return {"result": "stolen", "resource": resource, "amount": amount}

    # ------------------------------------------------------------------
    # Будівництво
    # ------------------------------------------------------------------
    def get_buildable_tiles(self, worker_id, kind):
        worker = self.units[worker_id]
        required_tile = config.BUILDING_REQUIRED_TILE.get(kind)

        if kind in ("Barracks", "Port"):
            # Мають лишатись вільними від юнітів (тренування / будівництво
            # кораблів), тому не можна будувати їх під собою.
            candidates = self._neighbors8(worker.row, worker.col)
        else:
            candidates = [(worker.row, worker.col)] + self._neighbors8(worker.row, worker.col)

        valid = []
        for r, c in candidates:
            if (r, c) in self.building_pos:
                continue
            tile = self.grid[r][c]

            if required_tile == "water":
                if tile != TILE_WATER:
                    continue
            elif required_tile is not None:
                if tile != required_tile:
                    continue
            else:
                if tile == TILE_WATER:
                    continue

            if kind == "Port":
                has_water_neighbor = any(
                    self.grid[nr][nc] == TILE_WATER for nr, nc in self._neighbors8(r, c)
                )
                if not has_water_neighbor:
                    continue

            valid.append((r, c))
        return valid

    def build_building(self, worker_id, kind, row, col):
        worker = self.units[worker_id]
        owner = self.players[worker.owner_id]
        cost = config.BUILDING_COSTS[kind]

        if self._is_exhausted(worker):
            return {"result": "blocked", "reason": "exhausted"}
        if kind == "HorseStable" and not owner.has_tech(config.HORSE_STABLE_REQUIRES_TECH):
            return {"result": "blocked", "reason": "tech_locked"}
        if (row, col) not in self.get_buildable_tiles(worker_id, kind):
            return {"result": "blocked", "reason": "invalid_tile"}
        if not owner.can_afford(cost):
            return {"result": "blocked", "reason": "cant_afford"}

        owner.pay(cost)
        uc = UnderConstruction(self._new_id(), worker.owner_id, row, col, kind)
        self.buildings[uc.id] = uc
        self.building_pos[(row, col)] = uc.id
        self._spend_ap(worker, self._worker_action_cost(worker.owner_id, config.ACTION_COST_BUILD))
        return {"result": "building_started", "building_id": uc.id}

    # ------------------------------------------------------------------
    # Виведення робітника з ресурсної будівлі назовні
    # ------------------------------------------------------------------
    def get_withdraw_tiles(self, building_id):
        b = self.buildings[building_id]
        return [
            (r, c) for r, c in self._neighbors8(b.row, b.col)
            if self._is_free_for_land_placement(r, c, b.owner_id)
        ]

    def withdraw_worker(self, building_id, row, col):
        building = self.buildings[building_id]
        if not isinstance(building, ResourceBuilding) or not building.workers_inside:
            return {"result": "blocked", "reason": "empty"}
        if (row, col) not in self.get_withdraw_tiles(building_id):
            return {"result": "blocked", "reason": "invalid_tile"}

        worker_id = building.workers_inside.pop(0)
        worker = self.units[worker_id]
        worker.row, worker.col = row, col
        self.unit_pos[(row, col)] = worker.id
        self._exhaust_fully(worker)

        choice = self._training_building_choice(row, col)
        if choice is not None:
            return {"result": choice, "worker_id": worker.id}

        self._auto_enter_if_possible(worker)
        return {"result": "withdrawn", "unit_id": worker_id}

    # ------------------------------------------------------------------
    # Прокачка ресурсної будівлі (5.2)
    # ------------------------------------------------------------------
    def start_building_upgrade(self, building_id):
        building = self.buildings[building_id]
        if not isinstance(building, ResourceBuilding):
            return {"result": "blocked", "reason": "invalid_building"}
        owner = self.players[building.owner_id]

        if building.upgraded or building.upgrading:
            return {"result": "blocked", "reason": "already_upgraded"}
        if not building.workers_inside:
            return {"result": "blocked", "reason": "no_workers"}
        cost = config.BUILDING_UPGRADE_COST[building.kind]
        if not owner.can_afford(cost):
            return {"result": "blocked", "reason": "cant_afford"}

        owner.pay(cost)
        building.upgrading = True
        building.upgrade_progress = 0
        return {"result": "upgrade_started"}

    def cancel_building_upgrade(self, building_id):
        building = self.buildings[building_id]
        if not isinstance(building, ResourceBuilding) or not building.upgrading:
            return {"result": "blocked"}
        owner = self.players[building.owner_id]
        refund = {
            res: config.BUILDING_UPGRADE_CANCEL_REFUND
            for res, amount in config.BUILDING_UPGRADE_COST[building.kind].items() if amount > 0
        }
        owner.add_resources(refund)
        building.upgrading = False
        building.upgrade_progress = 0
        return {"result": "upgrade_cancelled", "refund": refund}

    # ------------------------------------------------------------------
    # Дерево технологій (5.2.1) — спільне для ResourceBuilding/Smithy/
    # HorseStable/MagicSchool. Технології діють ГЛОБАЛЬНО на гравця,
    # щойно завершились (на початку наступного ходу).
    # ------------------------------------------------------------------
    def _tech_table_for(self, building):
        if isinstance(building, ResourceBuilding):
            return config.RESOURCE_BUILDING_TECHS.get(building.kind, {})
        if building.kind == "Smithy":
            return config.SMITHY_TECHS
        if building.kind == "HorseStable":
            return {"FasterHorses": config.FASTER_HORSES_COST}
        if building.kind == "MagicSchool":
            return {name: data["tech_cost"] for name, data in config.SPELLS.items() if data["tech_cost"] is not None}
        return {}

    def get_available_techs(self, building_id):
        building = self.buildings[building_id]
        owner = self.players[building.owner_id]
        result = {}
        for name, cost in self._tech_table_for(building).items():
            if name in owner.researched_techs:
                continue
            prereq = config.TECH_PREREQUISITE.get(name)
            if prereq and prereq not in owner.researched_techs:
                continue
            result[name] = cost
        return result

    def start_research(self, building_id, tech_name):
        building = self.buildings[building_id]
        owner = self.players[building.owner_id]

        if isinstance(building, ResourceBuilding) and building.upgrading:
            return {"result": "blocked", "reason": "upgrading"}
        if building.researching_tech is not None:
            return {"result": "blocked", "reason": "already_researching"}
        if tech_name not in self.get_available_techs(building_id):
            return {"result": "blocked", "reason": "invalid_tech"}

        cost = self._tech_table_for(building)[tech_name]
        if not owner.can_afford(cost):
            return {"result": "blocked", "reason": "cant_afford"}

        owner.pay(cost)
        building.researching_tech = tech_name
        return {"result": "research_started"}

    def cancel_research(self, building_id):
        building = self.buildings[building_id]
        if building.researching_tech is None:
            return {"result": "blocked"}
        owner = self.players[building.owner_id]
        cost = self._tech_table_for(building)[building.researching_tech]
        owner.add_resources(cost)
        building.researching_tech = None
        return {"result": "research_cancelled"}

    # ------------------------------------------------------------------
    # Найм воїна/лучника/вершника через Казарму (0 AP — сили пішли на тренування)
    # ------------------------------------------------------------------
    def promote_worker(self, worker_id, unit_type):
        worker = self.units[worker_id]
        owner = self.players[worker.owner_id]

        if worker.kind != "Worker":
            return {"result": "blocked", "reason": "invalid_unit"}

        if unit_type in config.WARRIOR_TYPES:
            cost = config.WARRIOR_COSTS[unit_type]
        elif unit_type == "Archer":
            cost = config.ARCHER_COST
        elif unit_type == "Horseman":
            if self.horse_used(worker.owner_id) + 1 > self.horse_limit(worker.owner_id):
                return {"result": "blocked", "reason": "horse_full"}
            cost = config.HORSEMAN_COST
        else:
            return {"result": "blocked", "reason": "invalid_type"}

        if not owner.can_afford(cost):
            return {"result": "blocked", "reason": "cant_afford"}
        owner.pay(cost)

        if unit_type in config.WARRIOR_TYPES:
            new_unit = Warrior(worker.id, worker.owner_id, worker.row, worker.col, unit_type, action_points=0)
        elif unit_type == "Archer":
            new_unit = Archer(worker.id, worker.owner_id, worker.row, worker.col, action_points=0)
        else:
            new_unit = Horseman(worker.id, worker.owner_id, worker.row, worker.col, action_points=0)

        self.units[worker.id] = new_unit
        return {"result": "promoted", "unit_id": new_unit.id}

    # ------------------------------------------------------------------
    # Школа магії (5.5.4) — найм мага
    # ------------------------------------------------------------------
    def hire_mage(self, worker_id):
        worker = self.units[worker_id]
        owner = self.players[worker.owner_id]

        if worker.kind != "Worker":
            return {"result": "blocked", "reason": "invalid_unit"}
        if not owner.can_afford(config.MAGE_HIRE_COST):
            return {"result": "blocked", "reason": "cant_afford"}

        owner.pay(config.MAGE_HIRE_COST)
        mage = Mage(worker.id, worker.owner_id, worker.row, worker.col, action_points=0)
        self.units[worker.id] = mage
        return {"result": "promoted", "unit_id": mage.id}

    # ------------------------------------------------------------------
    # Кузня (5.5.1/5.5.2) — катапульта спавниться ОКРЕМИМ юнітом поруч із
    # Кузнею (як корабель біля Порту), а НЕ перетворенням робітника — той
    # лишається на місці й може продовжувати працювати.
    # ------------------------------------------------------------------
    def get_catapult_spawn_tiles(self, smithy_id):
        smithy = self.buildings[smithy_id]
        return [
            (r, c) for r, c in self._neighbors8(smithy.row, smithy.col)
            if self._is_free_for_land_placement(r, c, smithy.owner_id)
        ]

    def spawn_catapult(self, smithy_id, row, col):
        smithy = self.buildings[smithy_id]
        owner = self.players[smithy.owner_id]

        if not owner.has_tech("HeavyArtillery"):
            return {"result": "blocked", "reason": "tech_locked"}
        if not owner.can_afford(config.CATAPULT_COST):
            return {"result": "blocked", "reason": "cant_afford"}
        if (row, col) not in self.get_catapult_spawn_tiles(smithy_id):
            return {"result": "blocked", "reason": "invalid_tile"}

        owner.pay(config.CATAPULT_COST)
        catapult = Catapult(self._new_id(), smithy.owner_id, row, col)
        self.units[catapult.id] = catapult
        self.unit_pos[(row, col)] = catapult.id
        return {"result": "spawned", "unit_id": catapult.id}

    # ------------------------------------------------------------------
    # Вежа (5.4 rework) — прокачка до одного з 3 типів
    # ------------------------------------------------------------------
    def get_tower_upgrade_options(self, tower_id):
        tower = self.buildings[tower_id]
        owner = self.players[tower.owner_id]
        if tower.tower_type is not None or tower.upgrading_to is not None:
            return []

        options = []
        for kind in config.TOWER_UPGRADE_KINDS:
            requirement = config.TOWER_UPGRADE_REQUIRES[kind]
            if requirement == "MagicSchoolBuilt":
                unlocked = any(
                    b.owner_id == tower.owner_id and b.kind == "MagicSchool" for b in self.buildings.values()
                )
            else:
                unlocked = owner.has_tech(requirement)
            if unlocked:
                options.append(kind)
        return options

    def start_tower_upgrade(self, tower_id, upgrade_kind):
        tower = self.buildings[tower_id]
        owner = self.players[tower.owner_id]
        if upgrade_kind not in self.get_tower_upgrade_options(tower_id):
            return {"result": "blocked", "reason": "invalid_upgrade"}
        cost = config.TOWER_UPGRADE_COST[upgrade_kind]
        if not owner.can_afford(cost):
            return {"result": "blocked", "reason": "cant_afford"}

        owner.pay(cost)
        tower.upgrading_to = upgrade_kind
        return {"result": "tower_upgrade_started"}

    # ------------------------------------------------------------------
    # Рух / атака / взаємодія (сусідня клітинка, як король) —
    # Worker, Warrior, Archer(лише рух), Horseman, Mage, Slime, Catapult(лише рух)
    # ------------------------------------------------------------------
    def get_valid_interactions(self, unit_id):
        """Повертає {(row, col): "move"/"attack"/"steal"/"enter_resource"/
        "barracks"/"magic_school"/"board_ship"}. Ship/CannonBoat
        сюди не потрапляють — у них своя логіка (плавання/дальня атака)."""
        unit = self.units[unit_id]
        if unit.kind in ("Ship", "CannonBoat") or self._is_exhausted(unit):
            return {}

        result = {}
        for r, c in self._neighbors8(unit.row, unit.col):
            b_id = self.building_pos.get((r, c))
            u_id = self.unit_pos.get((r, c))
            building = self.buildings.get(b_id) if b_id else None
            target_unit = self.units.get(u_id) if u_id else None

            # 1. Ворожий юніт -> атака. Archer/Catapult б'ють ЛИШЕ через
            #    ranged_attack (навіть по сусідній клітинці).
            if target_unit is not None and target_unit.owner_id != unit.owner_id:
                if unit.kind in _RANGED_ONLY_ATTACKERS:
                    continue
                if unit.kind == "Worker" and target_unit.kind in _SHIP_LIKE_KINDS:
                    continue
                result[(r, c)] = "attack"
                continue

            # 2. Ворожа будівля (не міст, не в процесі будівництва):
            #    Worker краде (якщо це грабіжний тип), Warrior/Horseman
            #    атакують, решта — не чіпають.
            if (building is not None and building.owner_id != unit.owner_id
                    and building.kind != "Bridge" and not isinstance(building, UnderConstruction)):
                if unit.kind == "Worker":
                    if building.kind in config.STEALABLE_BUILDING_KINDS:
                        result[(r, c)] = "steal"
                    continue
                if unit.kind in _MELEE_BUILDING_ATTACKERS:
                    result[(r, c)] = "attack"
                continue

            # Далі building (якщо є) свій, target_unit (якщо є) теж свій.

            # 3. Своя ресурсна будівля з місцем (і не в прокачці) + робітник -> вхід
            if (building is not None and isinstance(building, ResourceBuilding)
                    and unit.kind == "Worker" and building.has_space() and not building.upgrading
                    and target_unit is None):
                result[(r, c)] = "enter_resource"
                continue

            # 4. Своя Казарма + робітник -> вибір типу воїна/лучника/вершника
            if building is not None and building.kind == "Barracks" and unit.kind == "Worker":
                result[(r, c)] = "barracks"
                continue

            # 4b. Своя Школа магії + робітник -> найм мага
            if building is not None and building.kind == "MagicSchool" and unit.kind == "Worker":
                result[(r, c)] = "magic_school"
                continue

            # 4c. Своя Кузня — катапульта та технології замовляються через
            # вибір самої будівлі (як Порт для кораблів), робітнику тут
            # спеціальної дії не потрібно; головне — щоб він не "заходив"
            # на неї як на порожню клітинку (це виключає п.6 нижче).

            # 5. Свій корабель з вільним місцем -> посадка (Worker, Warrior,
            #    Archer, Horseman, Mage, Slime, Catapult — БУДЬ-ЯКИЙ наземний
            #    юніт; гарматні човни пасажирів не беруть, тому в них це
            #    відгалуження просто не виконується — target_unit.kind=="Ship" required)
            if (target_unit is not None and target_unit.kind == "Ship"
                    and target_unit.owner_id == unit.owner_id
                    and len(target_unit.passengers) < config.SHIP_CAPACITY):
                result[(r, c)] = "board_ship"
                continue

            # 6. Звичайний рух: порожньо, прохідно, і НЕ чужа/своя будівля
            #    (крім Bridge — той навмисно робить тайл прохідним).
            # Баг-фікс: раніше тут не було перевірки на "building is None",
            # тож робітник міг "заходити" на Castle/House/Tower/Smithy/
            # HorseStable як на порожню клітинку (жодна гілка вище цього не
            # ловила, бо в них немає власної worker-взаємодії).
            if (target_unit is None and (building is None or building.kind == "Bridge")
                    and self._is_passable_for_land_unit(r, c)):
                result[(r, c)] = "move"

        return result

    def interact(self, unit_id, row, col):
        options = self.get_valid_interactions(unit_id)
        action = options.get((row, col))
        unit = self.units[unit_id]

        if action == "move":
            self._move_unit(unit, row, col)
            return {"result": "moved"}
        if action == "attack":
            b_id = self.building_pos.get((row, col))
            u_id = self.unit_pos.get((row, col))
            if u_id is not None:
                return self._resolve_unit_attack(unit, self.units[u_id])
            return self._resolve_building_attack(unit, self.buildings[b_id])
        if action == "steal":
            building = self.buildings[self.building_pos[(row, col)]]
            return self.steal_resources(unit_id, building.id)
        if action == "enter_resource":
            building = self.buildings[self.building_pos[(row, col)]]
            self._enter_resource_building(unit, building, spend_ap=True)
            return {"result": "entered_resource"}
        if action == "barracks":
            return {"result": "barracks_choice", "worker_id": unit.id}
        if action == "magic_school":
            return {"result": "magic_school_choice", "worker_id": unit.id}
        if action == "board_ship":
            ship = self.units[self.unit_pos[(row, col)]]
            self._board_ship(unit, ship)
            return {"result": "boarded_ship"}

        return {"result": "blocked"}

    def _move_unit(self, unit, row, col):
        del self.unit_pos[(unit.row, unit.col)]
        unit.row, unit.col = row, col
        self.unit_pos[(row, col)] = unit.id
        self._spend_ap(unit, config.ACTION_COST_MOVE)

    def _enter_resource_building(self, worker, building, spend_ap):
        if self.unit_pos.get((worker.row, worker.col)) == worker.id:
            del self.unit_pos[(worker.row, worker.col)]
        worker.row, worker.col = building.row, building.col
        building.workers_inside.append(worker.id)
        if spend_ap:
            self._spend_ap(worker, config.ACTION_COST_MOVE)

    # ------------------------------------------------------------------
    # Дальня атака: Archer, Catapult (наземні, рухаються через
    # get_valid_interactions вище) та CannonBoat (плаває — див. move_cannon_boat)
    # ------------------------------------------------------------------
    def get_ranged_attack_tiles(self, unit_id):
        unit = self.units[unit_id]
        if self._is_exhausted(unit):
            return {}

        tiles = {}
        if unit.kind == "Archer":
            rng = (config.ARCHER_RANGE_UPGRADED if self.players[unit.owner_id].has_tech("Crossbow")
                   else config.ARCHER_RANGE)
            for u in self.units.values():
                if (u.owner_id != unit.owner_id and self.unit_pos.get((u.row, u.col)) == u.id
                        and max(abs(u.row - unit.row), abs(u.col - unit.col)) <= rng):
                    tiles[(u.row, u.col)] = "ranged_attack"
        elif unit.kind == "Catapult":
            for kind, target in self._siege_targets_in_range(
                    unit.row, unit.col, config.CATAPULT_MIN_RANGE, config.CATAPULT_MAX_RANGE, unit.owner_id):
                tiles[(target.row, target.col)] = "ranged_attack"
        elif unit.kind == "CannonBoat":
            for kind, target in self._siege_targets_in_range(
                    unit.row, unit.col, config.CANNON_BOAT_MIN_RANGE, config.CANNON_BOAT_MAX_RANGE, unit.owner_id):
                tiles[(target.row, target.col)] = "ranged_attack"
        return tiles

    def ranged_attack(self, unit_id, row, col):
        unit = self.units[unit_id]
        if (row, col) not in self.get_ranged_attack_tiles(unit_id):
            return {"result": "blocked"}

        if unit.kind == "Archer":
            target = self.units[self.unit_pos[(row, col)]]
            dmg = self._archer_damage_vs(target)
            self._spend_ap(unit, config.ATTACK_AP_COST["Archer"])
            died = self._apply_damage_to_unit(target, dmg)
            return {"result": "attacked", "damage": dmg, "target_died": died}

        # Catapult / CannonBoat — 1 AP, б'є все відразу (похід АБО атака).
        dmg = config.CATAPULT_ATTACK if unit.kind == "Catapult" else config.CANNON_BOAT_ATTACK
        b_id = self.building_pos.get((row, col))
        u_id = self.unit_pos.get((row, col))
        self._spend_ap(unit, unit.action_points)
        if u_id is not None:
            self._apply_damage_to_unit(self.units[u_id], dmg)
        else:
            building = self.buildings[b_id]
            died = building.take_damage(dmg)
            if died:
                self._destroy_building(building)
        return {"result": "attacked", "damage": dmg}

    # ------------------------------------------------------------------
    # Бій впритул (Worker/Warrior/Horseman/Mage/Slime — через interact)
    # ------------------------------------------------------------------
    def _compute_unit_attack_damage(self, attacker, defender):
        def_key = defender.warrior_type if (defender.kind == "Warrior" and defender.warrior_type) else defender.kind

        if attacker.kind == "Worker":
            return config.WORKER_ATTACK_VS_UNIT
        if attacker.kind == "Mage":
            return config.MAGE_ATTACK_VS_UNIT
        if attacker.kind == "Slime":
            return config.SLIME_ATTACK
        if attacker.kind == "Horseman":
            if defender.kind in ("Ship", "CannonBoat", "Catapult"):
                return config.HORSEMAN_ATTACK_VS_STRUCTURE
            return config.HORSEMAN_ATTACK_VS.get(def_key, 1)

        # Warrior
        atk_type = attacker.warrior_type
        if defender.kind == "Warrior":
            dmg = config.WARRIOR_DAMAGE[atk_type][defender.warrior_type]
        elif defender.kind in ("Ship", "CannonBoat"):
            dmg = config.WARRIOR_VS_SHIP_DAMAGE[atk_type]
        elif defender.kind == "Catapult":
            dmg = config.WARRIOR_VS_CATAPULT_DAMAGE[atk_type]
        elif defender.kind == "Horseman":
            dmg = config.HORSEMAN_DAMAGE_TAKEN.get(atk_type, 1)
            if atk_type == "Spear" and self.players[attacker.owner_id].has_tech("Alebards"):
                dmg += config.ALEBARDS_BONUS_VS_HORSEMAN
        elif defender.kind == "Archer":
            dmg = config.ARCHER_DAMAGE_TAKEN.get(atk_type, 1)
        else:  # Worker, Mage, Slime як захисники
            dmg = config.WARRIOR_VS_WORKER_DAMAGE

        if (atk_type == "Mace" and defender.kind in ("Ship", "CannonBoat", "Catapult")
                and self.players[attacker.owner_id].has_tech("BetterMaces")):
            dmg += config.BETTER_MACES_BONUS
        return dmg

    def _resolve_unit_attack(self, attacker, defender):
        ap_key = attacker.warrior_type if attacker.kind == "Warrior" else attacker.kind
        ap_cost = config.ATTACK_AP_COST.get(ap_key, 1)
        dmg = self._compute_unit_attack_damage(attacker, defender)
        self._spend_ap(attacker, ap_cost)
        died = self._apply_damage_to_unit(defender, dmg)
        return {"result": "attacked", "damage": dmg, "target_died": died}

    def _resolve_building_attack(self, attacker, building):
        if attacker.kind == "Horseman":
            dmg = config.HORSEMAN_ATTACK_VS_STRUCTURE
            ap_cost = config.ATTACK_AP_COST["Horseman"]
        else:
            dmg = config.WARRIOR_VS_BUILDING_DAMAGE.get(attacker.warrior_type, 1)
            if attacker.warrior_type == "Mace" and self.players[attacker.owner_id].has_tech("BetterMaces"):
                dmg += config.BETTER_MACES_BONUS
            ap_cost = config.ATTACK_AP_COST.get(attacker.warrior_type, 1)
        self._spend_ap(attacker, ap_cost)

        if isinstance(building, ResourceBuilding) and building.workers_inside:
            killed_id = building.workers_inside.pop()
            self.units.pop(killed_id, None)
            return {"result": "worker_killed_inside"}

        died = building.take_damage(dmg)
        if died:
            self._destroy_building(building)
        return {"result": "attacked_building", "damage": dmg, "target_died": died}

    def _destroy_building(self, building):
        if self.building_pos.get((building.row, building.col)) == building.id:
            del self.building_pos[(building.row, building.col)]
        del self.buildings[building.id]

        if isinstance(building, Castle):
            self._eliminate_player(building.owner_id)

    def _eliminate_player(self, owner_id):
        self.players[owner_id].alive = False

        for uid in [uid for uid, u in self.units.items() if u.owner_id == owner_id]:
            u = self.units[uid]
            if self.unit_pos.get((u.row, u.col)) == uid:
                del self.unit_pos[(u.row, u.col)]
            del self.units[uid]

        for bid in [bid for bid, b in self.buildings.items() if b.owner_id == owner_id]:
            b = self.buildings[bid]
            if self.building_pos.get((b.row, b.col)) == bid:
                del self.building_pos[(b.row, b.col)]
            del self.buildings[bid]

        self._check_victory()

    def _check_victory(self):
        alive = self.alive_player_ids()
        if len(alive) <= 1:
            self.game_over = True
            self.winner_id = alive[0] if alive else None

    def _remove_standalone_unit(self, unit):
        if self.unit_pos.get((unit.row, unit.col)) == unit.id:
            del self.unit_pos[(unit.row, unit.col)]
        self.units.pop(unit.id, None)

    # ------------------------------------------------------------------
    # Заклинання мага (5.5.4) — config.SPELLS описує вартість/дальність/тех.
    # ------------------------------------------------------------------
    def get_spell_target_tiles(self, mage_id, spell_name):
        mage = self.units[mage_id]
        if mage.kind != "Mage" or self._is_exhausted(mage) or spell_name not in config.SPELLS:
            return []

        owner = self.players[mage.owner_id]
        data = config.SPELLS[spell_name]
        if data["tech_cost"] is not None and not owner.has_tech(spell_name):
            return []
        rng = data["range"]

        def within(r, c):
            return max(abs(r - mage.row), abs(c - mage.col)) <= rng

        tiles = []
        if spell_name == "Heal":
            for u in self.units.values():
                if (u.owner_id == mage.owner_id and u.kind in ("Worker", "Warrior", "Archer", "Horseman")
                        and self.unit_pos.get((u.row, u.col)) == u.id and within(u.row, u.col)):
                    tiles.append((u.row, u.col))
        elif spell_name == "Freeze":
            for u in self.units.values():
                if (u.owner_id != mage.owner_id and self.unit_pos.get((u.row, u.col)) == u.id
                        and within(u.row, u.col)):
                    tiles.append((u.row, u.col))
        elif spell_name == "MagicShield":
            for u in self.units.values():
                if self.unit_pos.get((u.row, u.col)) == u.id and within(u.row, u.col):
                    tiles.append((u.row, u.col))
        elif spell_name == "YouShallNotPass":
            for b in self.buildings.values():
                if b.kind == "Bridge" and within(b.row, b.col):
                    tiles.append((b.row, b.col))
        elif spell_name == "Teleport":
            for u in self.units.values():
                if (u.owner_id == mage.owner_id and self.unit_pos.get((u.row, u.col)) == u.id
                        and within(u.row, u.col)):
                    tiles.append((u.row, u.col))
        elif spell_name == "SummonSlime":
            for r, c in self._neighbors8(mage.row, mage.col):
                if self._is_free_for_land_placement(r, c, mage.owner_id):
                    tiles.append((r, c))
        elif spell_name == "Thunder":
            for u in self.units.values():
                if (u.owner_id != mage.owner_id and u.kind in _SHIP_LIKE_KINDS
                        and self.unit_pos.get((u.row, u.col)) == u.id and within(u.row, u.col)):
                    tiles.append((u.row, u.col))
        return tiles

    def get_teleport_destination_tiles(self, mage_id, unit_row, unit_col):
        """Другий крок Телепортації — куди можна перенести обраного юніта
        (валідна вільна своя клітинка в межах config.TELEPORT_DISTANCE)."""
        mage = self.units[mage_id]
        tiles = []
        for r in range(self.rows):
            for c in range(self.cols):
                if max(abs(r - unit_row), abs(c - unit_col)) > config.TELEPORT_DISTANCE:
                    continue
                if self._is_free_for_land_placement(r, c, mage.owner_id):
                    tiles.append((r, c))
        return tiles

    def cast_spell(self, mage_id, spell_name, row, col, teleport_to=None):
        mage = self.units[mage_id]
        owner = self.players[mage.owner_id]
        data = config.SPELLS[spell_name]

        if (row, col) not in self.get_spell_target_tiles(mage_id, spell_name):
            return {"result": "blocked", "reason": "invalid_target"}
        use_cost = data["use_cost"]
        if not owner.can_afford(use_cost):
            return {"result": "blocked", "reason": "cant_afford"}

        if spell_name == "Heal":
            target = self.units[self.unit_pos[(row, col)]]
            target.heal(target.max_hp)
            target.frozen = False

        elif spell_name == "Freeze":
            self.units[self.unit_pos[(row, col)]].frozen = True

        elif spell_name == "MagicShield":
            self.units[self.unit_pos[(row, col)]].shielded = True

        elif spell_name == "YouShallNotPass":
            bridge = self.buildings[self.building_pos[(row, col)]]
            victim_id = self.unit_pos.get((row, col))
            if victim_id is not None:
                self._remove_standalone_unit(self.units[victim_id])
            self._destroy_building(bridge)

        elif spell_name == "Teleport":
            if teleport_to is None or teleport_to not in self.get_teleport_destination_tiles(mage_id, row, col):
                return {"result": "blocked", "reason": "invalid_destination"}
            target = self.units[self.unit_pos[(row, col)]]
            del self.unit_pos[(target.row, target.col)]
            target.row, target.col = teleport_to
            self.unit_pos[teleport_to] = target.id

        elif spell_name == "SummonSlime":
            slime = Slime(self._new_id(), mage.owner_id, row, col)
            self.units[slime.id] = slime
            self.unit_pos[(row, col)] = slime.id

        elif spell_name == "Thunder":
            target = self.units[self.unit_pos[(row, col)]]
            self._apply_damage_to_unit(target, config.THUNDER_DAMAGE_VS_SHIP)

        owner.pay(use_cost)
        self._spend_ap(mage, config.SPELL_AP_COST)
        return {"result": "cast", "spell": spell_name}

    # ------------------------------------------------------------------
    # Корабель: спавн / рух / посадка / висадка
    # ------------------------------------------------------------------
    def get_ship_spawn_tiles(self, port_id):
        port = self.buildings[port_id]
        return [
            (r, c) for r, c in self._neighbors8(port.row, port.col)
            if self.grid[r][c] == TILE_WATER and (r, c) not in self.unit_pos
        ]

    def spawn_ship(self, port_id, row, col):
        port = self.buildings[port_id]
        owner = self.players[port.owner_id]

        if not owner.can_afford(config.SHIP_COST):
            return {"result": "blocked", "reason": "cant_afford"}
        if (row, col) not in self.get_ship_spawn_tiles(port_id):
            return {"result": "blocked", "reason": "invalid_tile"}

        owner.pay(config.SHIP_COST)
        ship = Ship(self._new_id(), port.owner_id, row, col)
        self.units[ship.id] = ship
        self.unit_pos[(row, col)] = ship.id
        return {"result": "spawned", "unit_id": ship.id}

    def spawn_cannon_boat(self, port_id, row, col):
        """5.3 — доступно, лише коли прокачана технологія Heavy Artillery."""
        port = self.buildings[port_id]
        owner = self.players[port.owner_id]

        if not owner.has_tech("HeavyArtillery"):
            return {"result": "blocked", "reason": "tech_locked"}
        if not owner.can_afford(config.CANNON_BOAT_COST):
            return {"result": "blocked", "reason": "cant_afford"}
        if (row, col) not in self.get_ship_spawn_tiles(port_id):
            return {"result": "blocked", "reason": "invalid_tile"}

        owner.pay(config.CANNON_BOAT_COST)
        boat = CannonBoat(self._new_id(), port.owner_id, row, col)
        self.units[boat.id] = boat
        self.unit_pos[(row, col)] = boat.id
        return {"result": "spawned", "unit_id": boat.id}

    def get_ship_reachable_tiles(self, ship_id):
        ship = self.units[ship_id]
        start = (ship.row, ship.col)
        visited = {start: 0}
        frontier = [start]
        reachable = []

        while frontier:
            next_frontier = []
            for r, c in frontier:
                dist = visited[(r, c)]
                if dist >= config.SHIP_MOVE_RANGE:
                    continue
                for nr, nc in self._neighbors8(r, c):
                    if self.grid[nr][nc] != TILE_WATER or (nr, nc) in visited:
                        continue
                    visited[(nr, nc)] = dist + 1
                    next_frontier.append((nr, nc))
                    is_bridge = (
                        (nr, nc) in self.building_pos
                        and self.buildings[self.building_pos[(nr, nc)]].kind == "Bridge"
                    )
                    if (nr, nc) not in self.unit_pos and not is_bridge:
                        reachable.append((nr, nc))
            frontier = next_frontier

        return reachable

    def move_ship(self, ship_id, row, col):
        ship = self.units[ship_id]
        if ship.tired:
            return {"result": "blocked", "reason": "tired"}
        if (row, col) not in self.get_ship_reachable_tiles(ship_id):
            return {"result": "blocked", "reason": "invalid_tile"}

        del self.unit_pos[(ship.row, ship.col)]
        ship.row, ship.col = row, col
        self.unit_pos[(row, col)] = ship.id
        ship.tired = True
        return {"result": "moved"}

    def get_cannon_boat_reachable_tiles(self, boat_id):
        boat = self.units[boat_id]
        start = (boat.row, boat.col)
        visited = {start: 0}
        frontier = [start]
        reachable = []

        while frontier:
            next_frontier = []
            for r, c in frontier:
                dist = visited[(r, c)]
                if dist >= config.CANNON_BOAT_MOVE_RANGE:
                    continue
                for nr, nc in self._neighbors8(r, c):
                    if self.grid[nr][nc] != TILE_WATER or (nr, nc) in visited:
                        continue
                    visited[(nr, nc)] = dist + 1
                    next_frontier.append((nr, nc))
                    is_bridge = (
                        (nr, nc) in self.building_pos
                        and self.buildings[self.building_pos[(nr, nc)]].kind == "Bridge"
                    )
                    if (nr, nc) not in self.unit_pos and not is_bridge:
                        reachable.append((nr, nc))
            frontier = next_frontier

        return reachable

    def move_cannon_boat(self, boat_id, row, col):
        boat = self.units[boat_id]
        if self._is_exhausted(boat):
            return {"result": "blocked", "reason": "exhausted"}
        if (row, col) not in self.get_cannon_boat_reachable_tiles(boat_id):
            return {"result": "blocked", "reason": "invalid_tile"}

        del self.unit_pos[(boat.row, boat.col)]
        boat.row, boat.col = row, col
        self.unit_pos[(row, col)] = boat.id
        self._exhaust_fully(boat)
        return {"result": "moved"}

    def _board_ship(self, unit, ship):
        del self.unit_pos[(unit.row, unit.col)]
        ship.passengers.append(unit.id)
        self._spend_ap(unit, config.ACTION_COST_MOVE)

    def get_disembark_tiles(self, ship_id):
        """Лише власна суша (не можна висадитись на ворожу будівлю)."""
        ship = self.units[ship_id]
        return [
            (r, c) for r, c in self._neighbors8(ship.row, ship.col)
            if self.grid[r][c] != TILE_WATER and self._is_free_for_land_placement(r, c, ship.owner_id)
        ]

    def disembark(self, ship_id, passenger_id, row, col):
        ship = self.units[ship_id]
        if passenger_id not in ship.passengers:
            return {"result": "blocked"}
        if (row, col) not in self.get_disembark_tiles(ship_id):
            return {"result": "blocked"}

        passenger = self.units[passenger_id]
        ship.passengers.remove(passenger_id)
        passenger.row, passenger.col = row, col
        self.unit_pos[(row, col)] = passenger.id
        self._exhaust_fully(passenger)

        choice = self._training_building_choice(row, col)
        if choice is not None:
            return {"result": choice, "worker_id": passenger.id}

        self._auto_enter_if_possible(passenger)
        return {"result": "disembarked"}

    # ------------------------------------------------------------------
    # Порт як ринок (5.3) — обмін ресурсів, не потребує робітника/AP
    # ------------------------------------------------------------------
    def trade_at_port(self, port_id, give_resource, get_resource):
        port = self.buildings[port_id]
        owner = self.players[port.owner_id]

        if (give_resource, get_resource) not in config.PORT_TRADE_PAIRS:
            return {"result": "blocked", "reason": "invalid_pair"}
        if owner.resources.get(give_resource, 0) < config.PORT_TRADE_GIVE_AMOUNT:
            return {"result": "blocked", "reason": "cant_afford"}

        owner.resources[give_resource] -= config.PORT_TRADE_GIVE_AMOUNT
        owner.add_resources({get_resource: config.PORT_TRADE_GET_AMOUNT})
        return {"result": "traded"}

    # ------------------------------------------------------------------
    # Знесення будівлі (демонтаж) — повертає 1 кожного ресурсу з базової ціни
    # ------------------------------------------------------------------
    def _cost_kind_for_building(self, building):
        return building.target_kind if isinstance(building, UnderConstruction) else building.kind

    def get_demolish_refund(self, building_id):
        building = self.buildings.get(building_id)
        if building is None:
            return {}
        cost = config.BUILDING_COSTS.get(self._cost_kind_for_building(building))
        if not cost:
            return {}
        return {res: 1 for res, amount in cost.items() if amount > 0}

    def can_demolish(self, building_id):
        building = self.buildings.get(building_id)
        if building is None or building.kind in ("Castle", "Bridge"):
            return False
        if isinstance(building, ResourceBuilding) and (building.workers_inside or building.upgrading):
            return False
        if isinstance(building, Tower) and building.upgrading_to is not None:
            return False
        return True

    def demolish_building(self, building_id):
        if not self.can_demolish(building_id):
            return {"result": "blocked"}

        building = self.buildings[building_id]
        refund = self.get_demolish_refund(building_id)
        self.players[building.owner_id].add_resources(refund)

        if self.building_pos.get((building.row, building.col)) == building_id:
            del self.building_pos[(building.row, building.col)]
        del self.buildings[building_id]
        return {"result": "demolished", "refund": refund}
