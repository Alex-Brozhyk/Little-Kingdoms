import random
import time
import math

# Спроба імпорту конфігурацій для роботи штучного інтелекту
try:
    from config import COSTS, BOT_STEP_DELAY, HOUSING_PROVIDED, UNIT_DAMAGE_MATRIX
except ImportError:
    COSTS = {
        "Worker": {"gold": 0, "wood": 0, "food": 3},
        "Sword": {"gold": 3, "wood": 1, "food": 3},
        "Mace": {"gold": 3, "wood": 1, "food": 3},
        "Spear": {"gold": 3, "wood": 1, "food": 3},
        "Ship": {"gold": 3, "wood": 5, "food": 3},
        "House": {"gold": 0, "wood": 3, "food": 1},
        "Lumbermill": {"gold": 3, "wood": 0, "food": 0},
        "Windmill": {"gold": 0, "wood": 3, "food": 0},
        "Mine": {"gold": 0, "wood": 3, "food": 3},
        "Barracks": {"gold": 5, "wood": 3, "food": 3},
        "Tower": {"gold": 2, "wood": 5, "food": 0},
        "Bridge": {"gold": 0, "wood": 5, "food": 0},
        "Port": {"gold": 3, "wood": 8, "food": 3},
    }
    BOT_STEP_DELAY = 500


class BotAIController:
    """
    Клас штучного інтелекту бота.
    Керує прийняттям рішень для гравців-ботів у грі Little Kingdoms.
    """

    def __init__(self, game_view=None, game_state=None):
        """
        Ініціалізує контролер штучного інтелекту.
        :param game_view: Посилання на екран UI (GameViewFrame) для виклику after() та оновлення рендеру.
        :param game_state: Посилання на стан гри/моделі (якщо доступно).
        """
        self.game_view = game_view
        self.game_state = game_state
        self.step_delay = BOT_STEP_DELAY
        self.is_executing = False

    def execute_turn(self, player_color, on_turn_complete_callback):
        """
        Головна точка входу для запуску ходу бота.
        Використовує асинхронні затримки через root.after, щоб гравець бачив кроки бота.
        В кінці БОТ 100% ВИКЛИКАЄ on_turn_complete_callback (End Turn).
        """
        self.is_executing = True
        self.player_color = player_color
        self.on_complete = on_turn_complete_callback

        # Безпечне виконання з try...except, щоб хід НІКОЛИ не застрягав
        try:
            self._process_next_bot_action()
        except Exception as e:
            print(f"[Bot AI Error]: Emergency turn completion due to exception: {e}")
            self._finalize_turn()

    def _process_next_bot_action(self):
        """Проводиться 1 логічний крок бота, після чого планується наступний через після-затримку."""
        if not self.is_executing:
            self._finalize_turn()
            return

        action_performed = False

        try:
            # 1. Найм робітників (у Замку чи Будинках)
            action_performed = self._try_spawn_worker()

            # 2. Дії робітників (Будівництво, Ремонт, Вхід у будівлі, Рух до ресурсів/ворога)
            if not action_performed:
                action_performed = self._try_worker_actions()

            # 3. Трансформація у Казармі (Робітник -> Воїн)
            if not action_performed:
                action_performed = self._try_barracks_training()

            # 4. Дії Воїнів (Атака ворога, захід у Вежу або рух до ворожого Замку)
            if not action_performed:
                action_performed = self._try_warrior_actions()

            # 5. Дії Кораблів та розширення Мостів
            if not action_performed:
                action_performed = self._try_naval_and_bridge_expansion()

        except Exception as ex:
            print(f"[Bot AI Warning]: Step failed with error: {ex}")

        # Оновлюємо UI якщо є доступ
        if self.game_view and hasattr(self.game_view, "render_game_field"):
            self.game_view.render_game_field()

        # Якщо дію виконали — даємо затримку 0.5с для анімації та робимо наступний крок.
        # Якщо ніяких дій більше зробити неможливо — завершуємо хід!
        if action_performed and self.game_view:
            self.game_view.after(self.step_delay, self._process_next_bot_action)
        else:
            self._finalize_turn()

    def _try_spawn_worker(self):
        """Намагається замовити робітника у Замку чи Будинку, якщо вистачає їжі та ліміту житла."""
        if not self.game_view or not hasattr(self.game_view, "player_states"):
            return False

        p_state = self.game_view.player_states.get(self.player_color, {})
        food = p_state.get("food", 0)
        house_used = p_state.get("house_used", 0)
        house_max = p_state.get("house_max", 5)

        # Перевірка лімітів
        if food >= COSTS["Worker"]["food"] and house_used < house_max:
            # Знімаємо ресурси та спавнимо
            p_state["food"] -= COSTS["Worker"]["food"]
            p_state["house_used"] += 1
            print(f"[Bot {self.player_color}]: Spawned a Worker.")
            return True

        return False

    def _try_worker_actions(self):
        """Логіка робітників: збір ресурсів, будівництво інфраструктури, мостів або рух."""
        # Модель перевірки дій робітників
        # У разі наявності об'єктів гри тут викликаються їхні методи
        return False

    def _try_barracks_training(self):
        """Намагається перетворити робітника на Казармі на одного з воїнів (Sword/Mace/Spear)."""
        if not self.game_view or not hasattr(self.game_view, "player_states"):
            return False

        p_state = self.game_view.player_states.get(self.player_color, {})
        g = p_state.get("gold", 0)
        w = p_state.get("wood", 0)
        f = p_state.get("food", 0)

        # Вартість воїнів
        sword_cost = COSTS["Sword"]

        if g >= sword_cost["gold"] and w >= sword_cost["wood"] and f >= sword_cost["food"]:
            # Випадковий вибір типу воїна для різноманітності (Камінь-Ножиці-Папір)
            chosen_warrior = random.choice(["Sword", "Mace", "Spear"])
            p_state["gold"] -= sword_cost["gold"]
            p_state["wood"] -= sword_cost["wood"]
            p_state["food"] -= sword_cost["food"]
            print(f"[Bot {self.player_color}]: Trained warrior {chosen_warrior}.")
            return True

        return False

    def _try_warrior_actions(self):
        """Логіка воїнів: пошук ворога, атака або рух в сторону ворожого Замку."""
        return False

    def _try_naval_and_bridge_expansion(self):
        """
        Логіка подолання води:
        - Якщо до ворога 1 або 2 тайли води -> Будуємо Мости.
        - Якщо 3+ тайлів води -> Будуємо Порт та Корабель для перевезення.
        """
        if not self.game_view or not hasattr(self.game_view, "player_states"):
            return False

        p_state = self.game_view.player_states.get(self.player_color, {})
        wood = p_state.get("wood", 0)

        # Тимчасова логіка-симуляція розширення
        if wood >= COSTS["Bridge"]["wood"] and random.random() < 0.2:
            p_state["wood"] -= COSTS["Bridge"]["wood"]
            print(f"[Bot {self.player_color}]: Built a Bridge across water.")
            return True

        return False

    def _finalize_turn(self):
        """
        ГАРАНТОВАНЕ завершення ходу бота.
        Знімає прапор виконання та викликає callback для передачі ходу.
        """
        if self.is_executing:
            self.is_executing = False
            print(f"[Bot {self.player_color}]: Turn finished. Invoking End Turn.")
            if self.on_complete:
                self.on_complete()


if __name__ == "__main__":
    print("Testing BotAIController standalone module...")

    # Імітація об'єкта гри
    class MockGameView:
        def __init__(self):
            self.player_states = {
                "Blue": {"gold": 10, "wood": 10, "food": 10, "house_used": 1, "house_max": 5}
            }

        def render_game_field(self):
            pass

        def after(self, ms, func):
            # В тестах викликаємо одразу
            func()

    mock_ui = MockGameView()
    bot = BotAIController(game_view=mock_ui)

    def on_turn_end():
        print("SUCCESS: Callback on_turn_complete received!")

    bot.execute_turn("Blue", on_turn_end)
