import os
from datetime import date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
init_db()


# ---------- helpers ----------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Only the vendor (admin) can open that page.")
            return redirect(url_for("home"))
        return view(*args, **kwargs)
    return wrapped


def visible_customers(conn):
    """Admin sees all customers; a customer sees only themselves."""
    if session["role"] == "admin":
        return conn.execute(
            "SELECT id, name FROM users WHERE role = 'customer' ORDER BY name"
        ).fetchall()
    return conn.execute(
        "SELECT id, name FROM users WHERE id = ?", (session["user_id"],)
    ).fetchall()


def chosen_user_id():
    """A customer is always limited to their own id."""
    if session["role"] != "admin":
        return str(session["user_id"])
    return request.args.get("user_id", "")


# ---------- account pages ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        phone = request.form["phone"].strip()
        password = request.form["password"]

        if not name or not phone or len(password) < 6:
            flash("Enter your name, phone and a password of at least 6 characters.")
            return render_template("register.html", title="Register")

        conn = get_db()
        existing = conn.execute(
            "SELECT * FROM users WHERE phone = ?", (phone,)
        ).fetchone()

        if existing and existing["password_hash"]:
            conn.close()
            flash("That phone number is already registered. Please log in.")
            return redirect(url_for("login"))

        pw_hash = generate_password_hash(password)
        if existing:
            conn.execute(
                "UPDATE users SET name = ?, password_hash = ? WHERE id = ?",
                (name, pw_hash, existing["id"]),
            )
        else:
            has_admin = conn.execute(
                "SELECT 1 FROM users WHERE role = 'admin' LIMIT 1"
            ).fetchone()
            role = "customer" if has_admin else "admin"
            conn.execute(
                "INSERT INTO users (name, phone, password_hash, role) VALUES (?, ?, ?, ?)",
                (name, phone, pw_hash, role),
            )
        conn.commit()
        conn.close()
        flash("Account ready. Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html", title="Register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form["phone"].strip()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE phone = ?", (phone,)
        ).fetchone()
        conn.close()

        if user and user["password_hash"] and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            return redirect(url_for("home"))
        flash("Wrong phone number or password.")

    return render_template("login.html", title="Login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- main pages ----------
@app.route("/")
def home():
    return render_template("index.html", title="Dairy Tracker")


@app.route("/products")
@login_required
def products():
    conn = get_db()
    rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    conn.close()
    return render_template("products.html", title="Products", products=rows)


@app.route("/customers", methods=["GET", "POST"])
@admin_required
def customers():
    conn = get_db()
    if request.method == "POST":
        name = request.form["name"].strip()
        phone = request.form["phone"].strip()
        if name and phone:
            exists = conn.execute(
                "SELECT 1 FROM users WHERE phone = ?", (phone,)
            ).fetchone()
            if exists:
                flash("A user with that phone number already exists.")
            else:
                conn.execute(
                    "INSERT INTO users (name, phone, role) VALUES (?, ?, 'customer')",
                    (name, phone),
                )
                conn.commit()
        conn.close()
        return redirect(url_for("customers"))
    rows = conn.execute(
        "SELECT * FROM users WHERE role = 'customer' ORDER BY name"
    ).fetchall()
    conn.close()
    return render_template("customers.html", title="Customers", customers=rows)


@app.route("/entries/new", methods=["GET", "POST"])
@admin_required
def new_entry():
    conn = get_db()
    if request.method == "POST":
        user_id = request.form["user_id"]
        product_id = request.form["product_id"]
        entry_date = request.form["entry_date"]
        quantity = float(request.form["quantity"])
        quality = request.form["quality"]
        fat = request.form["fat_percent"].strip()
        fat_percent = float(fat) if fat else None

        product = conn.execute(
            "SELECT rate_per_unit FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        cost = round(quantity * product["rate_per_unit"], 2)

        conn.execute(
            """INSERT INTO entries
               (user_id, product_id, entry_date, quantity, cost, quality, fat_percent)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, product_id, entry_date, quantity, cost, quality, fat_percent),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("entries"))

    customers = conn.execute(
        "SELECT id, name FROM users WHERE role = 'customer' ORDER BY name"
    ).fetchall()
    products = conn.execute("SELECT id, name, unit FROM products ORDER BY name").fetchall()
    conn.close()
    return render_template(
        "new_entry.html",
        title="New Entry",
        customers=customers,
        products=products,
        today=date.today().isoformat(),
    )


@app.route("/entries")
@login_required
def entries():
    conn = get_db()
    query = """SELECT e.entry_date, u.name AS customer, p.name AS product, p.unit,
                      e.quantity, e.cost, e.quality, e.fat_percent
               FROM entries e
               JOIN users u ON u.id = e.user_id
               JOIN products p ON p.id = e.product_id"""
    params = ()
    if session["role"] != "admin":
        query += " WHERE e.user_id = ?"
        params = (session["user_id"],)
    query += " ORDER BY e.entry_date DESC, e.id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("entries.html", title="Daily Entries", entries=rows)


@app.route("/report")
@login_required
def report():
    conn = get_db()
    customers = visible_customers(conn)

    month = request.args.get("month") or date.today().strftime("%Y-%m")
    user_id = chosen_user_id()
    summary = None
    breakdown = []
    quality_rows = []

    if user_id:
        breakdown = conn.execute(
            """SELECT p.name AS product, p.unit,
                      SUM(e.quantity) AS total_qty,
                      SUM(e.cost) AS total_cost,
                      COUNT(*) AS days
               FROM entries e
               JOIN products p ON p.id = e.product_id
               WHERE e.user_id = ? AND strftime('%Y-%m', e.entry_date) = ?
               GROUP BY p.id
               ORDER BY p.name""",
            (user_id, month),
        ).fetchall()

        milk = conn.execute(
            """SELECT COALESCE(SUM(e.quantity), 0) AS litres,
                      AVG(e.fat_percent) AS avg_fat
               FROM entries e
               JOIN products p ON p.id = e.product_id
               WHERE e.user_id = ? AND p.name = 'Milk'
                 AND strftime('%Y-%m', e.entry_date) = ?""",
            (user_id, month),
        ).fetchone()

        quality_rows = conn.execute(
            """SELECT e.quality, COUNT(*) AS n
               FROM entries e
               JOIN products p ON p.id = e.product_id
               WHERE e.user_id = ? AND p.name = 'Milk'
                 AND strftime('%Y-%m', e.entry_date) = ?
               GROUP BY e.quality""",
            (user_id, month),
        ).fetchall()

        customer = conn.execute(
            "SELECT name FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        summary = {
            "customer": customer["name"] if customer else "",
            "milk_litres": milk["litres"],
            "avg_fat": milk["avg_fat"],
            "total_cost": sum(r["total_cost"] for r in breakdown),
        }

    conn.close()
    return render_template(
        "report.html",
        title="Monthly Report",
        customers=customers,
        month=month,
        user_id=user_id,
        summary=summary,
        breakdown=breakdown,
        quality_rows=quality_rows,
    )

def shift_month(month, delta):
    """Return 'YYYY-MM' moved by `delta` months, or None if month is invalid."""
    try:
        year, mon = (int(x) for x in month.split("-"))
    except ValueError:
        return None
    if not 1 <= mon <= 12:
        return None
    index = year * 12 + (mon - 1) + delta
    return f"{index // 12}-{index % 12 + 1:02d}"


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    customers = visible_customers(conn)

    month = request.args.get("month") or date.today().strftime("%Y-%m")
    if shift_month(month, 0) is None:
        month = date.today().strftime("%Y-%m")
    user_id = chosen_user_id()

    data = {
        "labels": [], "litres": [], "costs": [],
        "product_labels": [], "product_costs": [],
        "quality_labels": [], "quality_counts": [],
    }
    stats = None
    customer_name = ""

    if user_id:
        # Daily totals for the two main charts
        rows = conn.execute(
            """SELECT e.entry_date AS d,
                      SUM(CASE WHEN p.name = 'Milk' THEN e.quantity ELSE 0 END) AS litres,
                      SUM(e.cost) AS cost
               FROM entries e
               JOIN products p ON p.id = e.product_id
               WHERE e.user_id = ? AND strftime('%Y-%m', e.entry_date) = ?
               GROUP BY e.entry_date
               ORDER BY e.entry_date""",
            (user_id, month),
        ).fetchall()
        data["labels"] = [r["d"] for r in rows]
        data["litres"] = [r["litres"] for r in rows]
        data["costs"] = [r["cost"] for r in rows]

        # Spend by product
        product_rows = conn.execute(
            """SELECT p.name AS product, SUM(e.cost) AS cost
               FROM entries e
               JOIN products p ON p.id = e.product_id
               WHERE e.user_id = ? AND strftime('%Y-%m', e.entry_date) = ?
               GROUP BY p.id
               ORDER BY cost DESC""",
            (user_id, month),
        ).fetchall()
        data["product_labels"] = [r["product"] for r in product_rows]
        data["product_costs"] = [r["cost"] for r in product_rows]

        # Milk quality (number of entries per rating)
        quality_rows = conn.execute(
            """SELECT COALESCE(e.quality, 'Not recorded') AS quality, COUNT(*) AS n
               FROM entries e
               JOIN products p ON p.id = e.product_id
               WHERE e.user_id = ? AND p.name = 'Milk'
                 AND strftime('%Y-%m', e.entry_date) = ?
               GROUP BY 1""",
            (user_id, month),
        ).fetchall()
        data["quality_labels"] = [r["quality"] for r in quality_rows]
        data["quality_counts"] = [r["n"] for r in quality_rows]

        # Average fat % for milk
        avg_fat = conn.execute(
            """SELECT AVG(e.fat_percent) AS avg_fat
               FROM entries e
               JOIN products p ON p.id = e.product_id
               WHERE e.user_id = ? AND p.name = 'Milk'
                 AND strftime('%Y-%m', e.entry_date) = ?""",
            (user_id, month),
        ).fetchone()["avg_fat"]

        # Milk bought in the previous month, for the comparison card
        prev_litres = conn.execute(
            """SELECT COALESCE(SUM(e.quantity), 0) AS litres
               FROM entries e
               JOIN products p ON p.id = e.product_id
               WHERE e.user_id = ? AND p.name = 'Milk'
                 AND strftime('%Y-%m', e.entry_date) = ?""",
            (user_id, shift_month(month, -1)),
        ).fetchone()["litres"]

        total_litres = sum(data["litres"])
        total_cost = sum(data["costs"])
        milk_days = sum(1 for x in data["litres"] if x > 0)
        change = None
        if prev_litres > 0:
            change = round((total_litres - prev_litres) / prev_litres * 100, 1)

        stats = {
            "total_litres": total_litres,
            "total_cost": total_cost,
            "days": len(data["labels"]),
            "avg_litres": total_litres / milk_days if milk_days else 0,
            "avg_fat": avg_fat,
            "change": change,
        }

        c = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
        customer_name = c["name"] if c else ""

    conn.close()
    return render_template(
        "dashboard.html",
        title="Dashboard",
        customers=customers,
        month=month,
        prev_month=shift_month(month, -1),
        next_month=shift_month(month, 1),
        user_id=user_id,
        customer_name=customer_name,
        stats=stats,
        **data,
    )


if __name__ == "__main__":
    app.run(debug=True)