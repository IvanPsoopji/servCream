#pvp_server
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import threading
import time
import random
import logging
from collections import deque

app = Flask(__name__)
CORS(app)

# Використовуємо deque для швидших операцій з чергою
# Глобальні змінні
matchmaking_queue = deque()
active_battles = {}
queue_lock = threading.Lock()
battle_lock = threading.Lock()

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def matchmaking_worker():
    """Покращений воркер для пошуку матчів"""
    while True:
        try:
            with queue_lock:
                if len(matchmaking_queue) >= 2:
                    player1 = matchmaking_queue.popleft()
                    player2 = matchmaking_queue.popleft()

                    battle_id = f"battle_{int(time.time())}_{random.randint(1000, 9999)}"

                    with battle_lock:
                        active_battles[battle_id] = {
                            "player1": player1,
                            "player2": player2,
                            "status": "waiting",
                            "created_at": time.time()
                        }

                    logger.info(f"Created battle {battle_id}: "
                                f"{player1['username']} vs {player2['username']}")

        except Exception as e:
            logger.error(f"Matchmaking error: {e}")
        finally:
            time.sleep(0.5)


@app.route('/join_queue', methods=['POST'])
def join_queue():
    try:
        player = request.json
        with queue_lock:
            # Перевірка на повторне додавання
            if any(p['user_id'] == player['user_id'] for p in matchmaking_queue):
                return jsonify({"status": "already_in_queue"})

            matchmaking_queue.append(player)
            logger.info(f"Player {player['username']} added to queue. Size: {len(matchmaking_queue)}")

            return jsonify({
                "status": "searching",
                "queue_size": len(matchmaking_queue)
            })

    except Exception as e:
        logger.error(f"Join queue error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/check_battle', methods=['POST'])
def check_battle():
    try:
        user_id = request.json.get('user_id')
        with battle_lock:
            # Пошук активного бою для гравця
            for battle_id, battle in active_battles.items():
                if battle['status'] == 'waiting':
                    if user_id in [battle['player1']['user_id'], battle['player2']['user_id']]:
                        opponent = (battle['player2'] if user_id == battle['player1']['user_id']
                                    else battle['player1'])
                        return jsonify({
                            "status": "found",
                            "battle_id": battle_id,
                            "opponent": opponent
                        })

        return jsonify({
            "status": "searching",
            "queue_size": len(matchmaking_queue)
        })

    except Exception as e:
        logger.error(f"Check battle error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Запускаємо воркер у окремому потоці
    threading.Thread(target=matchmaking_worker, daemon=True).start()

    # Налаштування Flask
    app.run(
        host='0.0.0.0',
        port=5000,
        threaded=True,
        use_reloader=False  # Вимкнути reloader для коректної роботи потоків
    )

@app.route("/cancel_queue", methods=["POST"])
def cancel_queue():
    try:
        user_id = request.json.get("user_id")

        with queue_lock:
            global matchmaking_queue
            matchmaking_queue = [p for p in matchmaking_queue if p["user_id"] != user_id]

        return jsonify({"status": "cancelled"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/battle/<battle_id>")
def battle_page(battle_id):
    user_id = request.args.get("user_id")

    if battle_id not in active_battles:
        return "Бій не знайдено або вже завершено", 404

    battle = active_battles[battle_id]

    if user_id not in [battle["player1"]["user_id"], battle["player2"]["user_id"]]:
        return "Ви не є учасником цього бою", 403

    # Позначаємо, що гравець зайшов на сторінку бою
    if "players_ready" not in battle:
        battle["players_ready"] = []

    if user_id not in battle["players_ready"]:
        battle["players_ready"].append(user_id)

    # Якщо обидва гравці готові - починаємо бій
    if len(battle.get("players_ready", [])) == 2:
        battle["status"] = "started"

    # Визначаємо, хто є суперником
    opponent = battle["player2"] if user_id == battle["player1"]["user_id"] else battle["player1"]

    return render_template("pvp_battle.html",
                           battle_id=battle_id,
                           user_id=user_id,
                           opponent=opponent)

if __name__ == "__main__":
    print("🛠️ Запуск PvP сервера...")

    # Запускаємо потік для пошуку матчів (використовуємо правильну назву функції)
    threading.Thread(target=matchmaking_worker, daemon=True).start()

    # Запускаємо Flask сервер
    app.run(host="0.0.0.0", port=5000, threaded=True)