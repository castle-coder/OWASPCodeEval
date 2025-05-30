from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
import uvicorn
from datetime import datetime

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

def get_db():
    conn = sqlite3.connect('shop.db')
    return conn

@app.on_event("startup")
async def startup_event():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0
        )
    ''')
    cursor.execute('''
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cart_items (
            cart_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL
        )
    ''')
    cursor.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'user', 'user@example.com', '<hashed>', 0, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'user')
    ''')
    cursor.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'admin', 'admin@example.com', '<hashed>', 1, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
    ''')
    cursor.execute('''
        INSERT INTO products (name, description, price, stock, is_deleted)
        SELECT 'T-Shirt', '100% cotton, comfy tee', 19.99, 100, 0
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'T-Shirt')
    ''')
    cursor.execute('''
        INSERT INTO products (name, description, price, stock, is_deleted)
        SELECT 'Mug', 'Ceramic mug with logo', 12.50, 50, 0
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'Mug')
    ''')
    cursor.execute('''
        INSERT INTO products (name, description, price, stock, is_deleted)
        SELECT 'Sticker', 'Vinyl sticker pack (5 pcs)', 4.99, 200, 0
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'Sticker')
    ''')
    conn.commit()
    conn.close()

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

@app.get("/login/{member_id}")
async def login(request: Request, member_id: str):
    request.session['member_id'] = member_id
    request.session['is_admin'] = (member_id == 'admin')
    return render_template_string('<html><body><h1>Logged in as {{ member_id }}</h1></body></html>', member_id=member_id)

@app.get("/shop")
async def shop(request: Request):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE is_deleted = 0 ORDER BY created_at DESC')
    products = cursor.fetchall()
    conn.close()
    return render_template_string('''
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
    ''', products=products)

@app.get("/shop/{product_id}")
async def shop_product(request: Request, product_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE product_id = ? AND is_deleted = 0', (product_id,))
    product = cursor.fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if request.session.get('member_id'):
        return render_template_string('''
            <html>
            <body>
                <h1>{{ product[1] }}</h1>
                <p>{{ product[2] }}</p>
                <p>Price: {{ product[3] }}</p>
                <p>Stock: {{ product[4] }}</p>
                <form action="/cart/add/{{ product[0] }}" method="post">
                    <input type="number" name="quantity" value="1" min="1">
                    <input type="submit" value="Add to Cart">
                </form>
            </body>
            </html>
        ''', product=product)
    else:
        return render_template_string('''
            <html>
            <body>
                <h1>{{ product[1] }}</h1>
                <p>{{ product[2] }}</p>
                <p>Price: {{ product[3] }}</p>
                <p>Stock: {{ product[4] }}</p>
            </body>
            </html>
        ''', product=product)

@app.post("/cart/add/{product_id}")
async def add_to_cart(request: Request, product_id: int, quantity: int = Form(1)):
    member_id = request.session.get('member_id')
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM cart_items WHERE owner_id = ? AND product_id = ?', (member_id, product_id))
    cart_item = cursor.fetchone()
    if cart_item:
        cursor.execute('UPDATE cart_items SET quantity = ? WHERE cart_item_id = ?', (cart_item[3] + quantity, cart_item[0]))
    else:
        cursor.execute('INSERT INTO cart_items (owner_id, product_id, quantity) VALUES (?, ?, ?)', (member_id, product_id, quantity))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Item added to cart</h1></body></html>')

@app.get("/cart")
async def view_cart(request: Request):
    member_id = request.session.get('member_id')
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM cart_items WHERE owner_id = ?', (member_id,))
    cart_items = cursor.fetchall()
    total = sum(item[3] * item[4] for item in cart_items)
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>My Cart</h1>
            <ul>
                {% for item in cart_items %}
                <li>{{ item[5] }} x {{ item[4] }} = {{ item[3] * item[4] }}</li>
                <form action="/cart/remove/{{ item[0] }}" method="post">
                    <input type="submit" value="Remove">
                </form>
                {% endfor %}
            </ul>
            <p>Total: {{ total }}</p>
            <form action="/cart/checkout" method="post">
                <input type="submit" value="Checkout">
            </form>
        </body>
        </html>
    ''', cart_items=cart_items, total=total)

@app.post("/cart/remove/{cart_item_id}")
async def remove_from_cart(request: Request, cart_item_id: int):
    member_id = request.session.get('member_id')
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM cart_items WHERE cart_item_id = ? AND owner_id = ?', (cart_item_id, member_id))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Item removed from cart</h1></body></html>')

@app.post("/cart/checkout")
async def checkout(request: Request):
    member_id = request.session.get('member_id')
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM cart_items WHERE owner_id = ?', (member_id,))
    cart_items = cursor.fetchall()
    total = sum(item[3] * item[4] for item in cart_items)
    cursor.execute('INSERT INTO orders (buyer_id, total_amount, status) VALUES (?, ?, ?)', (member_id, total, 'PLACED'))
    order_id = cursor.lastrowid
    for item in cart_items:
        cursor.execute('INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)', (order_id, item[2], item[3], item[4]))
    cursor.execute('DELETE FROM cart_items WHERE owner_id = ?', (member_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Order placed</h1></body></html>')

@app.get("/orders")
async def list_orders(request: Request):
    member_id = request.session.get('member_id')
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE buyer_id = ? OR is_admin = 1 ORDER BY created_at DESC', (member_id, member_id))
    orders = cursor.fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>My Orders</h1>
            <ul>
                {% for order in orders %}
                <li><a href="/orders/{{ order[0] }}">{{ order[0] }} - {{ order[5] }} - {{ order[4] }}</a></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', orders=orders)

@app.get("/orders/{order_id}")
async def view_order(request: Request, order_id: int):
    member_id = request.session.get('member_id')
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE order_id = ? AND (buyer_id = ? OR is_admin = 1)', (order_id, member_id, member_id))
    order = cursor.fetchone()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,))
    order_items = cursor.fetchall()
    total = sum(item[3] * item[4] for item in order_items)
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>Order {{ order_id }}</h1>
            <p>Status: {{ order[4] }}</p>
            <p>Total: {{ total }}</p>
            <ul>
                {% for item in order_items %}
                <li>{{ item[3] }} x {{ item[4] }} = {{ item[3] * item[4] }}</li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', order_id=order_id, order=order, order_items=order_items, total=total)

@app.get("/admin/products/create")
async def create_product_form(request: Request):
    member_id = request.session.get('member_id')
    if not member_id or not request.session.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not authorized")
    return render_template_string('''
        <html>
        <body>
            <h1>Create Product</h1>
            <form action="/admin/products/create" method="post">
                <input type="text" name="name" placeholder="Name" required>
                <input type="text" name="description" placeholder="Description" required>
                <input type="number" name="price" placeholder="Price" required>
                <input type="number" name="stock" placeholder="Stock" required>
                <input type="submit" value="Create">
            </form>
        </body>
        </html>
    ''')

@app.post("/admin/products/create")
async def create_product(request: Request):
    member_id = request.session.get('member_id')
    if not member_id or not request.session.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not authorized")
    name = request.form.get('name')
    description = request.form.get('description')
    price = request.form.get('price')
    stock = request.form.get('stock')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO products (name, description, price, stock) VALUES (?, ?, ?, ?)', (name, description, price, stock))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Product created</h1></body></html>')

@app.get("/admin/products/edit/{product_id}")
async def edit_product_form(request: Request, product_id: int):
    member_id = request.session.get('member_id')
    if not member_id or not request.session.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE product_id = ?', (product_id,))
    product = cursor.fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>Edit Product</h1>
            <form action="/admin/products/edit/{{ product_id }}" method="post">
                <input type="text" name="name" value="{{ product[1] }}" required>
                <input type="text" name="description" value="{{ product[2] }}" required>
                <input type="number" name="price" value="{{ product[3] }}" required>
                <input type="number" name="stock" value="{{ product[4] }}" required>
                <input type="submit" value="Update">
            </form>
        </body>
        </html>
    ''', product_id=product_id, product=product)

@app.post("/admin/products/edit/{product_id}")
async def edit_product(request: Request, product_id: int):
    member_id = request.session.get('member_id')
    if not member_id or not request.session.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not authorized")
    name = request.form.get('name')
    description = request.form.get('description')
    price = request.form.get('price')
    stock = request.form.get('stock')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET name = ?, description = ?, price = ?, stock = ? WHERE product_id = ?', (name, description, price, stock, product_id))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Product updated</h1></body></html>')

@app.post("/admin/products/delete/{product_id}")
async def delete_product(request: Request, product_id: int):
    member_id = request.session.get('member_id')
    if not member_id or not request.session.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET is_deleted = 1 WHERE product_id = ?', (product_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Product deleted</h1></body></html>')

@app.get("/admin/orders")
async def list_admin_orders(request: Request):
    member_id = request.session.get('member_id')
    if not member_id or not request.session.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders ORDER BY created_at DESC')
    orders = cursor.fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>All Orders</h1>
            <ul>
                {% for order in orders %}
                <li><a href="/orders/{{ order[0] }}">{{ order[0] }} - {{ order[5] }} - {{ order[4] }}</a></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', orders=orders)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)
```

This code provides a complete implementation of a community website's shop service using FastAPI and sqlite3, with all HTML defined directly inside the `app.py` file. The code includes all the required features and endpoints, as well as automatic table creation and dummy data insertion upon initializati