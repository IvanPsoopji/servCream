from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import time
import random
from database import db

app = Flask(__name__)
CORS(app)  # Дозволяємо крос-доменні запити

# Глобальні змінні для черги та активних боїв
matchmaking_queue = []
active_battles = {}
queue_lock = threading.Lock()  # Для потокобезпечної роботи з чергою


def run_matchmaking():
    """Функція для пошуку суперників"""
    while True:
        try:
            with queue_lock:
                # Якщо в черзі є як мінімум 2 гравці
                if len(matchmaking_queue) >= 2:
                    player1 = matchmaking_queue.pop(0)
                    player2 = matchmaking_queue.pop(0)

                    battle_id = f"battle_{int(time.time())}_{random.randint(1000, 9999)}"

                    active_battles[battle_id] = {
                        "player1": player1,
                        "player2": player2,
                        "start_time": time.time(),
                        "status": "waiting"
                    }

                    print(f"⚔️ Початок бою {battle_id}: {player1['username']} vs {player2['username']}")

        except Exception as e:
            print(f"Помилка у matchmaking: {e}")

        time.sleep(1)


@app.route("/join_queue", methods=["POST"])
def join_queue():
    try:
        player_data = request.json

        with queue_lock:
            # Перевіряємо, чи гравець вже в черзі
            if any(p["user_id"] == player_data["user_id"] for p in matchmaking_queue):
                return jsonify({
                    "status": "already_in_queue",
                    "queue_size": len(matchmaking_queue)
                })

            matchmaking_queue.append(player_data)

            print(f"➕ Гравець {player_data['username']} доданий в чергу. Очікують: {len(matchmaking_queue)}")

            return jsonify({
                "status": "searching",
                "queue_size": len(matchmaking_queue)
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/check_battle", methods=["POST"])
def check_battle():
    try:
        user_id = request.json.get("user_id")

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

        return jsonify({"status": "searching"})

    except Exception as e:
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

    return "Бойова сторінка"  # Тут буде ваш HTML/JS для бою


if __name__ == "__main__":
    print("🛠️ Запуск PvP сервера...")

    # Запускаємо потік для пошуку матчів
    threading.Thread(target=run_matchmaking, daemon=True).start()

    # Запускаємо Flask сервер
    app.run(host="0.0.0.0", port=5000, threaded=True)