from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
from datetime import datetime

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

# Database connection
conn = sqlite3.connect('shop.db')
c = conn.cursor()

# Create tables
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    email TEXT NOT NULL,
    password TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT 0,
    is_deleted BOOLEAN DEFAULT 0
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER NOT NULL,
    is_deleted BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS cart_items (
    cart_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(user_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    status TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (buyer_id) REFERENCES users(user_id)
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
)
''')

# Insert dummy data
c.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)", ('user', 'user@example.com', '<hashed>', 0, 0))
c.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)", ('admin', 'admin@example.com', '<hashed>', 1, 0))
c.execute("INSERT INTO products (name, description, price, stock, is_deleted) VALUES (?, ?, ?, ?, ?)", ('T-Shirt', '100% cotton, comfy tee', 19.99, 100, 0))
c.execute("INSERT INTO products (name, description, price, stock, is_deleted) VALUES (?, ?, ?, ?, ?)", ('Mug', 'Ceramic mug with logo', 12.50, 50, 0))
c.execute("INSERT INTO products (name, description, price, stock, is_deleted) VALUES (?, ?, ?, ?, ?)", ('Sticker', 'Vinyl sticker pack (5 pcs)', 4.99, 200, 0))
conn.commit()

# Routes
@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    request.session["member_id"] = member_id
    request.session["is_admin"] = False
    return RedirectResponse("/shop")

@app.get("/shop")
async def shop(request: Request):
    if "member_id" not in request.session:
        return "Please log in."
    c.execute("SELECT * FROM products WHERE is_deleted = 0 ORDER BY created_at DESC")
    products = c.fetchall()
    html = """
    <html>
    <body>
        <h1>Shop</h1>
        <ul>
            {% for product in products %}
                <li><a href="/shop/{{ product[0] }}">{{ product[1] }}</a></li>
            {% endfor %}
        </ul>
    </body>
    </html>
    """
    return render_template_string(html, products=products)

@app.get("/shop/{product_id}")
async def view_product(request: Request, product_id: int):
    if "member_id" not in request.session:
        return "Please log in."
    c.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
    product = c.fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    html = """
    <html>
    <body>
        <h1>{{ product[1] }}</h1>
        <p>{{ product[2] }}</p>
        <p>Price: ${{ product[3] }}</p>
        <p>Stock: {{ product[4] }}</p>
        <form action="/cart/add/{{ product[0] }}" method="post">
            <input type="number" name="quantity" value="1">
            <input type="submit" value="Add to Cart">
        </form>
    </body>
    </html>
    """
    return render_template_string(html, product=product)

@app.post("/cart/add/{product_id}")
async def add_to_cart(request: Request, product_id: int, quantity: int = Form(1)):
    if "member_id" not in request.session:
        return "Please log in."
    c.execute("SELECT stock FROM products WHERE product_id = ?", (product_id,))
    stock = c.fetchone()[0]
    if stock < quantity:
        return "Not enough stock."
    c.execute("INSERT INTO cart_items (owner_id, product_id, quantity) VALUES (?, ?, ?)", (request.session["member_id"], product_id, quantity))
    conn.commit()
    return RedirectResponse("/cart")

@app.get("/cart")
async def view_cart(request: Request):
    if "member_id" not in request.session:
        return "Please log in."
    c.execute("SELECT cart_items.cart_item_id, products.name, cart_items.quantity, cart_items.quantity * products.price AS subtotal FROM cart_items JOIN products ON cart_items.product_id = products.product_id WHERE cart_items.owner_id = ?", (request.session["member_id"],))
    cart_items = c.fetchall()
    total = sum(item[3] for item in cart_items)
    html = """
    <html>
    <body>
        <h1>My Cart</h1>
        <ul>
            {% for item in cart_items %}
                <li>{{ item[1] }} ({{ item[2] }}) - ${{ item[3] }}</li>
                <form action="/cart/remove/{{ item[0] }}" method="post">
                    <input type="submit" value="Remove">
                </form>
            {% endfor %}
        </ul>
        <p>Total: ${{ total }}</p>
        <form action="/cart/checkout" method="post">
            <input type="submit" value="Checkout">
        </form>
    </body>
    </html>
    """
    return render_template_string(html, cart_items=cart_items, total=total)

@app.post("/cart/remove/{cart_item_id}")
async def remove_from_cart(request: Request, cart_item_id: int):
    if "member_id" not in request.session:
        return "Please log in."
    c.execute("DELETE FROM cart_items WHERE cart_item_id = ?", (cart_item_id,))
    conn.commit()
    return RedirectResponse("/cart")

@app.post("/cart/checkout")
async def checkout(request: Request):
    if "member_id" not in request.session:
        return "Please log in."
    c.execute("SELECT SUM(quantity * price) AS total FROM cart_items JOIN products ON cart_items.product_id = products.product_id WHERE cart_items.owner_id = ?", (request.session["member_id"],))
    total = c.fetchone()[0]
    c.execute("INSERT INTO orders (buyer_id, total_amount, status) VALUES (?, ?, 'PLACED')", (request.session["member_id"], total))
    order_id = c.lastrowid
    c.execute("SELECT cart_items.cart_item_id, cart_items.quantity, products.price FROM cart_items JOIN products ON cart_items.product_id = products.product_id WHERE cart_items.owner_id = ?", (request.session["member_id"],))
    cart_items = c.fetchall()
    for item in cart_items:
        c.execute("INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)", (order_id, item[0], item[1], item[2]))
    c.execute("DELETE FROM cart_items WHERE owner_id = ?", (request.session["member_id"],))
    conn.commit()
    return RedirectResponse("/orders")

@app.get("/orders")
async def view_orders(request: Request):
    if "member_id" not in request.session:
        return "Please log in."
    if not request.session["is_admin"]:
        c.execute("SELECT * FROM orders WHERE buyer_id = ?", (request.session["member_id"],))
    else:
        c.execute("SELECT * FROM orders ORDER BY created_at DESC")
    orders = c.fetchall()
    html = """
    <html>
    <body>
        <h1>My Orders</h1>
        <ul>
            {% for order in orders %}
                <li><a href="/orders/{{ order[0] }}">{{ order[0] }} - Total: ${{ order[2] }} - Status: {{ order[3] }}</a></li>
            {% endfor %}
        </ul>
    </body>
    </html>
    """
    return render_template_string(html, orders=orders)

@app.get("/orders/{order_id}")
async def view_order(request: Request, order_id: int):
    if "member_id" not in request.session:
        return "Please log in."
    if not request.session["is_admin"]:
        c.execute("SELECT * FROM orders WHERE order_id = ? AND buyer_id = ?", (order_id, request.session["member_id"],))
    else:
        c.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    order = c.fetchone()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    c.execute("SELECT products.name, order_items.quantity, order_items.quantity * products.price AS subtotal FROM order_items JOIN products ON order_items.product_id = products.product_id WHERE order_items.order_id = ?", (order_id,))
    order_items = c.fetchall()
    total = sum(item[2] for item in order_items)
    html = """
    <html>
    <body>
        <h1>Order {{ order_id }}</h1>
        <p>Total: ${{ total }}</p>
        <ul>
            {% for item in order_items %}
                <li>{{ item[0] }} ({{ item[1] }}) - ${{ item[2] }}</li>
            {% endfor %}
        </ul>
    </body>
    </html>
    """
    return render_template_string(html, order_items=order_items, total=total)

@app.get("/admin/products/create")
async def create_product(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return "Permission denied."
    html = """
    <html>
    <body>
        <h1>Create Product</h1>
        <form action="/admin/products/create" method="post">
            <input type="text" name="name" required>
            <input type="text" name="description" required>
            <input type="number" name="price" required>
            <input type="number" name="stock" required>
            <input type="submit" value="Create">
        </form>
    </body>
    </html>
    """
    return render_template_string(html)

@app.post("/admin/products/create")
async def create_product_post(request: Request, name: str = Form(...), description: str = Form(...), price: float = Form(...), stock: int = Form(...)):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return "Permission denied."
    c.execute("INSERT INTO products (name, description, price, stock) VALUES (?, ?, ?, ?)", (name, description, price, stock))
    conn.commit()
    return RedirectResponse("/admin/products")

@app.get("/admin/products/edit/{product_id}")
async def edit_product(request: Request, product_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return "Permission denied."
    c.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
    product = c.fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    html = """
    <html>
    <body>
        <h1>Edit Product</h1>
        <form action="/admin/products/edit/{{ product[0] }}" method="post">
            <input type="text" name="name" value="{{ product[1] }}" required>
            <input type="text" name="description" value="{{ product[2] }}" required>
            <input type="number" name="price" value="{{ product[3] }}" required>
            <input type="number" name="stock" value="{{ product[4] }}" required>
            <input type="submit" value="Update">
        </form>
    </body>
    </html>
    """
    return render_template_string(html, product=product)

@app.post("/admin/products/edit/{product_id}")
async def edit_product_post(request: Request, product_id: int, name: str = Form(...), description: str = Form(...), price: float = Form(...), stock: int = Form(...)):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return "Permission denied."
    c.execute("UPDATE products SET name = ?, description = ?, price = ?, stock = ? WHERE product_id = ?", (name, description, price, stock, product_id))
    conn.commit()
    return RedirectResponse("/admin/products")

@app.post("/admin/products/delete/{product_id}")
async def delete_product(request: Request, product_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return "Permission denied."
    c.execute("UPDATE products SET is_deleted = 1 WHERE product_id = ?", (product_id,))
    conn.commit()
    return RedirectResponse("/admin/products")

@app.get("/admin/products")
async def view_products(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return "Permission denied."
    c.execute("SELECT * FROM products WHERE is_deleted = 0")
    products = c.fetchall()
    html = """
    <html>
    <body>
        <h1>Products</h1>
        <ul>
            {% for product in products %}
                <li>{{ product[1] }} - <a href="/admin/products/edit/{{ product[0] }}">Edit</a> | <form action="/admin/products/delete/{{ product[0] }}" method="post"><input type="submit" value="Delete"></form></li>
            {% endfor %}
        </ul>
        <a href="/admin/products/create">Create Product</a>
    </body>
    </html>
    """
    return render_template_string(html, products=products)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)