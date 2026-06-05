import os
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
from db import get_connection, init_db, query, USE_POSTGRES

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "healthtrack-key")

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        existing = query("SELECT id FROM users WHERE email=?", (f["email"],), fetchone=True)
        if existing:
            return render_template("register.html", error="Email already registered.")
        pw = generate_password_hash(f["password"])
        query("""
            INSERT INTO users (first_name, last_name, email, password_hash)
            VALUES (?,?,?,?)
        """, (f["first_name"], f["last_name"], f["email"], pw), commit=True)
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        f = request.form
        user = query("SELECT * FROM users WHERE email=?", (f["email"],), fetchone=True)
        if not user or not check_password_hash(user["password_hash"], f["password"]):
            return render_template("login.html", error="Invalid email or password.")
        session["user_id"] = user["id"]
        session["username"] = user["first_name"]
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    if request.method == "POST":
        session["water"] = request.form.get("water", 0)
        session["sleep"] = request.form.get("sleep", 0)
        session["steps"] = request.form.get("steps", 0)
    return render_template("dashboard.html",
        username=session.get("username", "Guest"),
        water=session.get("water", 0),
        sleep=session.get("sleep", 0),
        steps=session.get("steps", 0)
    )


@app.route("/habits", methods=["GET", "POST"])
def habits():
    uid = session.get("user_id")
    if not uid:
        return redirect(url_for("login"))

    if request.method == "POST":
        f = request.form
        query("""
            INSERT INTO habits (user_id, name, category, frequency, goal, description, reminder_time)
            VALUES (?,?,?,?,?,?,?)
        """, (uid, f["name"], f.get("category", "fitness"),
              f.get("frequency", "daily"), f.get("goal", ""),
              f.get("description", ""), f.get("reminder_time") or None), commit=True)
        return redirect(url_for("habits"))

    today = str(date.today())
    habits_list = query("SELECT * FROM habits WHERE user_id=?", (uid,), fetchall=True)

    for h in habits_list:
        log = query(
            "SELECT id FROM habit_logs WHERE habit_id=? AND logged_date=?",
            (h["id"], today), fetchone=True
        )
        h["done_today"] = 1 if log else 0

    return render_template("habits.html", habits=habits_list)


@app.route("/habits/<int:habit_id>/complete", methods=["POST"])
def complete_habit(habit_id):
    uid = session.get("user_id")
    if not uid:
        return redirect(url_for("login"))
    today = str(date.today())
    existing = query(
        "SELECT id FROM habit_logs WHERE habit_id=? AND logged_date=?",
        (habit_id, today), fetchone=True
    )
    if existing:
        query("DELETE FROM habit_logs WHERE habit_id=? AND logged_date=?",
              (habit_id, today), commit=True)
    else:
        query("INSERT INTO habit_logs (habit_id, user_id, logged_date) VALUES (?,?,?)",
              (habit_id, uid, today), commit=True)
    return redirect(url_for("habits"))


@app.route("/habits/<int:habit_id>/delete", methods=["POST"])
def delete_habit(habit_id):
    uid = session.get("user_id")
    if not uid:
        return redirect(url_for("login"))
    query("DELETE FROM habits WHERE id=? AND user_id=?", (habit_id, uid), commit=True)
    return redirect(url_for("habits"))


@app.route("/api/reminders")
def get_reminders():
    uid = session.get("user_id")
    if not uid:
        return jsonify([])
    reminders = query(
        "SELECT id, name, reminder_time FROM habits WHERE user_id=? AND reminder_time IS NOT NULL AND reminder_time != ''",
        (uid,), fetchall=True
    )
    return jsonify([{"id": r["id"], "name": r["name"], "time": r["reminder_time"]} for r in reminders])


@app.route("/analytics")
def analytics():
    uid = session.get("user_id")
    habits_list = []
    category_counts = [0, 0, 0, 0, 0]
    cats = ["fitness", "nutrition", "sleep", "mental", "hydration"]
    total = 0
    completed = 0
    dates = []
    daily_completions = []
    weekly = [0, 0, 0, 0, 0, 0, 0]

    if uid:
        habits_list = query("SELECT * FROM habits WHERE user_id=?", (uid,), fetchall=True)
        total = len(habits_list)

        for h in habits_list:
            if h["category"] in cats:
                category_counts[cats.index(h["category"])] += 1
            cnt = query("SELECT COUNT(*) AS cnt FROM habit_logs WHERE habit_id=?",
                        (h["id"],), fetchone=True)
            h["total_logs"] = cnt["cnt"] if cnt else 0

        rows = query("""
            SELECT logged_date, COUNT(*) AS cnt
            FROM habit_logs WHERE user_id=?
            GROUP BY logged_date ORDER BY logged_date
        """, (uid,), fetchall=True)
        dates = [str(r["logged_date"]) for r in rows]
        daily_completions = [r["cnt"] for r in rows]

        if USE_POSTGRES:
            dow_rows = query("""
                SELECT EXTRACT(DOW FROM logged_date::date) AS dow, COUNT(*) AS cnt
                FROM habit_logs WHERE user_id=?
                GROUP BY dow
            """, (uid,), fetchall=True)
        else:
            dow_rows = query("""
                SELECT strftime('%w', logged_date) AS dow, COUNT(*) AS cnt
                FROM habit_logs WHERE user_id=?
                GROUP BY dow
            """, (uid,), fetchall=True)

        dow_map = {str(int(r["dow"])): r["cnt"] for r in dow_rows}
        weekly = [dow_map.get(str(i), 0) for i in [1, 2, 3, 4, 5, 6, 0]]

        total_logs = query("SELECT COUNT(*) AS cnt FROM habit_logs WHERE user_id=?",
                           (uid,), fetchone=True)
        completed = total_logs["cnt"] if total_logs else 0

    completion_rate = round(completed / (total * 30) * 100) if total > 0 else 0

    return render_template("analytics.html",
        username=session.get("username", "Guest"),
        habits=habits_list,
        stats={
            "best_streak": 0,
            "completion_rate": min(completion_rate, 100),
            "active_habits": total,
            "total_logs": completed
        },
        chart_data={
            "dates": dates,
            "daily_completions": daily_completions,
            "categories": ["Fitness", "Nutrition", "Sleep", "Mental", "Hydration"],
            "category_counts": category_counts,
            "weekly": weekly,
            "habit_names": [h["name"] for h in habits_list],
            "habit_logs": [h["total_logs"] for h in habits_list]
        }
    )


if __name__ == "__main__":
    init_db()
    print("✅ Database ready.")
    import webbrowser, threading
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=True)
