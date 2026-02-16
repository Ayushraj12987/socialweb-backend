from flask import Flask, request, jsonify
import requests
import sqlite3
import os
from datetime import datetime

app = Flask(_name_)

# ================= ENV VARIABLES =================
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
LOGS_ID = os.getenv("LOGS_ID")

DB_NAME = "social_booster.db"
# =================================================


# ========= DATABASE =========
def get_balance(uid):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    return bal[0] if bal else 0


def update_balance(uid, amount):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, uid))
    conn.commit()
    conn.close()


def save_order(order_id, uid, service, link, qty, price):
    conn = sqlite3.connect(DB_NAME)
    conn.execute(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
        (order_id, uid, service, link, qty, price, "Processing")
    )
    conn.commit()
    conn.close()


# ========= ROUTES =========

@app.route("/")
def home():
    return "Social Booster Backend Running 🚀"


@app.route("/services", methods=["GET"])
def services():
    response = requests.post(API_URL, data={
        "key": API_KEY,
        "action": "services"
    })
    return jsonify(response.json())


@app.route("/order", methods=["POST"])
def place_order():
    data = request.json

    uid = int(data["user_id"])
    service = int(data["service"])
    link = data["link"]
    quantity = int(data["quantity"])

    services = requests.post(API_URL, data={
        "key": API_KEY,
        "action": "services"
    }).json()

    selected = next((s for s in services if s["service"] == service), None)

    if not selected:
        return jsonify({"status": "error", "message": "Service not found"})

    if quantity < selected["min"] or quantity > selected["max"]:
        return jsonify({"status": "error", "message": "Invalid quantity"})

    rate = float(selected["rate"])
    base_cost = (rate / 1000) * quantity
    final_price = round(base_cost + (base_cost * 0.20), 2)

    balance = get_balance(uid)

    if balance < final_price:
        return jsonify({"status": "error", "message": "Insufficient balance"})

    order_response = requests.post(API_URL, data={
        "key": API_KEY,
        "action": "add",
        "service": service,
        "link": link,
        "quantity": quantity
    }).json()

    if "order" not in order_response:
        return jsonify({"status": "error", "message": order_response})

    order_id = order_response["order"]

    update_balance(uid, final_price)
    save_order(order_id, uid, service, link, quantity, final_price)

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": LOGS_ID,
            "text": f"""🔔 NEW ORDER

👤 User: {uid}
🆔 Order ID: {order_id}
🔢 Qty: {quantity}
💰 ₹{final_price}
📅 {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
"""
        }
    )

    return jsonify({
        "status": "success",
        "order_id": order_id,
        "price": final_price
    })


if _name_ == "_main_":
    app.run(host="0.0.0.0", port=5000)
