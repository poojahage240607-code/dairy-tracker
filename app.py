from flask import Flask, render_template
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


if __name__ == "__main__":
    app.run(debug=True)