from datetime import date
from flask import Flask, render_template, request, redirect, url_for
from db import get_db, init_db

app = Flask(__name__)
init_db()


@app.route("/")
def home():
    return render_template("index.html", title="Dairy Tracker")


@app.route("/products")
def products():
    conn = get_db()
    rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    conn.close()
    return render_template("products.html", title="Products", products=rows)


@app.route("/customers", methods=["GET", "POST"])
def customers():
    conn = get_db()
    if request.method == "POST":
        name = request.form["name"].strip()
        phone = request.form["phone"].strip()
        if name:
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
def entries():
    conn = get_db()
    rows = conn.execute(
        """SELECT e.entry_date, u.name AS customer, p.name AS product, p.unit,
                  e.quantity, e.cost, e.quality, e.fat_percent
           FROM entries e
           JOIN users u ON u.id = e.user_id
           JOIN products p ON p.id = e.product_id
           ORDER BY e.entry_date DESC, e.id DESC"""
    ).fetchall()
    conn.close()
    return render_template("entries.html", title="Daily Entries", entries=rows)


if __name__ == "__main__":
    app.run(debug=True)