#pvp_server
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import threading
import time
import random
from collections import deque

app = Flask(__name__)
CORS(app)

# Використовуємо deque для швидших операцій з чергою
matchmaking_queue = deque()
active_battles = {}
queue_lock = threading.Lock()
battle_lock = threading.Lock()


def run_matchmaking():
    """Покращена функція пошуку суперників"""
    while True:
        try:
            with queue_lock:
                # Якщо в черзі є як мінімум 2 гравці
                if len(matchmaking_queue) >= 2:
                    player1 = matchmaking_queue.popleft()
                    player2 = matchmaking_queue.popleft()

                    battle_id = f"battle_{int(time.time())}_{random.randint(1000, 9999)}"

                    with battle_lock:
                        active_battles[battle_id] = {
                            "player1": player1,
                            "player2": player2,
                            "start_time": time.time(),
                            "status": "waiting",
                            "players_ready": []
                        }

                    print(f"⚔️ Створено бій {battle_id}:")
                    print(f"   {player1['username']} (lvl {player1['level']})")
                    print(f"   vs")
                    print(f"   {player2['username']} (lvl {player2['level']})")

        except Exception as e:
            print(f"Помилка у matchmaking: {e}")

        time.sleep(0.5)  # Зменшуємо інтервал перевірки


@app.route("/join_queue", methods=["POST"])
def join_queue():
    try:
        player_data = request.json
        user_id = player_data["user_id"]

        with queue_lock:
            # Перевіряємо, чи гравець вже в черзі
            if any(p["user_id"] == user_id for p in matchmaking_queue):
                return jsonify({
                    "status": "already_in_queue",
                    "queue_size": len(matchmaking_queue)
                })

            matchmaking_queue.append(player_data)
            print(f"➕ {player_data['username']} доданий в чергу. Розмір черги: {len(matchmaking_queue)}")

            return jsonify({
                "status": "searching",
                "queue_size": len(matchmaking_queue)
            })

    except Exception as e:
        print(f"Помилка в join_queue: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/check_battle", methods=["POST"])
def check_battle():
    try:
        user_id = request.json.get("user_id")

        with battle_lock:
            for battle_id, battle in active_battles.items():
                if battle["status"] == "waiting":
                    if user_id == battle["player1"]["user_id"]:
                        return jsonify({
                            "status": "found",
                            "battle_id": battle_id,
                            "opponent": battle["player2"]
                        })
                    elif user_id == battle["player2"]["user_id"]:
                        return jsonify({
                            "status": "found",
                            "battle_id": battle_id,
                            "opponent": battle["player1"]
                        })

        return jsonify({"status": "searching", "queue_size": len(matchmaking_queue)})

    except Exception as e:
        print(f"Помилка в check_battle: {e}")
        return jsonify({"error": str(e)}), 500


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

    # Запускаємо потік для пошуку матчів
    threading.Thread(target=run_matchmaking, daemon=True).start()

    # Запускаємо Flask сервер
    app.run(host="0.0.0.0", port=5000, threaded=True)