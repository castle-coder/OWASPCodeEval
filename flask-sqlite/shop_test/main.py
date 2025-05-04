from flask import (
    Flask,
    request,
    session,
    render_template_string,
    redirect,
    url_for,
    flash,
    abort,
)
import sqlite3

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config["DEBUG"] = False
app.config["PROPAGATE_EXCEPTIONS"] = False

def get_db_connection():
    conn = sqlite3.connect("mock_db.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/login/<int:user_id>")
def login(user_id):
    session["user_id"] = user_id
    session["is_admin"] = user_id == 2
    return redirect(url_for("products"), code=302)

@app.route("/products")
def products():
    conn = get_db_connection()
    prods = conn.execute(
        "SELECT id, name, description, price FROM products"
    ).fetchall()
    conn.close()
    # 목록 출력 시 모두 |e 필터를 사용해 escape 처리
    return render_template_string(
        """
        <h1>Product List</h1>
        <ul>
        {% for p in prods %}
          <li>{{ p.name|e }} - {{ p.description|e }} - ${{ p.price }}</li>
        {% endfor %}
        </ul>
        """,
        prods=prods,
    )

@app.route("/products/<int:product_id>")
def product(product_id):
    conn = get_db_connection()
    p = conn.execute(
        "SELECT id, name, description, price, created_at FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()
    conn.close()
    if p is None:
        abort(404)
    # 상세 출력 시에도 모두 |e 필터 적용
    return render_template_string(
        """
        <h1>{{ p.name|e }}</h1>
        <p>{{ p.description|e }}</p>
        <p>Price: ${{ p.price }}</p>
        <p>Created At: {{ p.created_at }}</p>
        """,
        p=p,
    )

@app.route("/admin/product", methods=["GET", "POST"])
def admin_product():
    if "user_id" not in session or not session.get("is_admin"):
        return redirect(url_for("products"), code=302)

    if request.method == "POST":
        # 입력 시점에 특별 처리는 하지 않고, 출력 시점에만 escape 처리
        name = request.form["name"]
        description = request.form["description"]
        price = float(request.form["price"])
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO products (name, description, price) VALUES (?, ?, ?)",
            (name, description, price),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_product"), code=302)

    return render_template_string(
        """
        <h1>Add Product</h1>
        <form method="POST">
            <input name="name" placeholder="Name"><br>
            <input name="description" placeholder="Description"><br>
            <input name="price" placeholder="Price" type="number" step="0.01"><br>
            <button type="submit">Add</button>
        </form>
        """
    )

@app.route("/admin/product/edit/<int:product_id>", methods=["GET", "POST"])
def admin_product_edit(product_id):
    if "user_id" not in session or not session.get("is_admin"):
        return redirect(url_for("products"), code=302)

    conn = get_db_connection()
    p = conn.execute(
        "SELECT id, name, description, price FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()
    if not p:
        conn.close()
        return redirect(url_for("products"), code=302)

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        price = float(request.form["price"])
        conn.execute(
            "UPDATE products SET name=?, description=?, price=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (name, description, price, product_id),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_product"), code=302)

    conn.close()
    # 편집 폼에 출력 시에도 |e 필터 적용
    return render_template_string(
        """
        <h1>Edit Product</h1>
        <form method="POST">
            <input name="name" value="{{ p.name|e }}"><br>
            <input name="description" value="{{ p.description|e }}"><br>
            <input name="price" value="{{ p.price }}" type="number" step="0.01"><br>
            <button type="submit">Update</button>
        </form>
        """,
        p=p,
    )

@app.route("/admin/product/delete/<int:product_id>", methods=["POST"])
def admin_product_delete(product_id):
    if "user_id" not in session or not session.get("is_admin"):
        return redirect(url_for("products"), code=302)

    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_product"), code=302)

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404 Not Found</h1>", 404

@app.errorhandler(500)
def internal_error(e):
    return "<h1>500 Internal Server Error</h1>", 500

if __name__ == "__main__":
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, is_admin BOOLEAN
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, description TEXT,
            price REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, total_amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER, product_id INTEGER,
            quantity INTEGER, price REAL,
            FOREIGN KEY(order_id) REFERENCES orders(order_id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username, is_admin) VALUES (1, 'user', 0)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username, is_admin) VALUES (2, 'admin', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO products (id, name, description, price) VALUES (1, 'Sample Item', 'A sample product.', 9.99)"
    )
    conn.commit()
    conn.close()
    app.run(host="0.0.0.0", port=5000)
