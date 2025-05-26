from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlite3 import connect, Row
from jinja2 import Template
import uvicorn
import datetime

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

def get_db():
    conn = connect("mock_db.sqlite3")
    conn.row_factory = Row
    return conn

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

@app.on_event("startup")
def startup_event():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0
        )
    ''')
    conn.execute('''
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
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cart_items (
            cart_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL
        )
    ''')
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'user', 'user@example.com', '<hashed>', 0, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'user')
    ''')
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'admin', 'admin@example.com', '<hashed>', 1, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
    ''')
    conn.execute('''
        INSERT INTO products (name, description, price, stock, is_deleted)
        SELECT 'T-Shirt', '100% cotton, comfy tee', 19.99, 100, 0
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'T-Shirt')
    ''')
    conn.execute('''
        INSERT INTO products (name, description, price, stock, is_deleted)
        SELECT 'Mug', 'Ceramic mug with logo', 12.50, 50, 0
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'Mug')
    ''')
    conn.execute('''
        INSERT INTO products (name, description, price, stock, is_deleted)
        SELECT 'Sticker', 'Vinyl sticker pack (5 pcs)', 4.99, 200, 0
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'Sticker')
    ''')
    conn.commit()
    conn.close()

@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    request.session["member_id"] = member_id
    request.session["is_admin"] = False
    return render_template_string('<html><body>Logged in as member {{ member_id }}</body></html>', member_id=member_id)

@app.get("/shop")
async def shop(request: Request):
    conn = get_db()
    products = conn.execute('SELECT * FROM products WHERE is_deleted = 0 ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>Shop</h1>
            <ul>
                {% for product in products %}
                <li><a href="/shop/{{ product.product_id }}">{{ product.name }}</a></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', products=products)

@app.get("/shop/{product_id}")
async def shop_product(request: Request, product_id: int):
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE product_id = ? AND is_deleted = 0', (product_id,)).fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    member_id = request.session.get("member_id")
    is_admin = request.session.get("is_admin")
    if member_id:
        return render_template_string('''
            <html>
            <body>
                <h1>{{ product.name }}</h1>
                <p>{{ product.description }}</p>
                <p>Price: ${{ product.price }}</p>
                <p>Stock: {{ product.stock }}</p>
                <form action="/cart/add/{{ product.product_id }}" method="post">
                    <label for="quantity">Quantity:</label>
                    <input type="number" id="quantity" name="quantity" value="1">
                    <button type="submit">Add to Cart</button>
                </form>
            </body>
            </html>
        ''', product=product)
    else:
        return render_template_string('''
            <html>
            <body>
                <h1>{{ product.name }}</h1>
                <p>{{ product.description }}</p>
                <p>Price: ${{ product.price }}</p>
                <p>Stock: {{ product.stock }}</p>
            </body>
            </html>
        ''', product=product)

@app.post("/cart/add/{product_id}")
async def add_to_cart(request: Request, product_id: int, quantity: int = Form(1)):
    member_id = request.session.get("member_id")
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    conn.execute('''
        INSERT OR REPLACE INTO cart_items (owner_id, product_id, quantity)
        VALUES (?, ?, ?)
    ''', (member_id, product_id, quantity))
    conn.commit()
    conn.close()
    return render_template_string('<html><body>Item added to cart</body></html>')

@app.get("/cart")
async def view_cart(request: Request):
    member_id = request.session.get("member_id")
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cart_items = conn.execute('SELECT * FROM cart_items WHERE owner_id = ?', (member_id,)).fetchall()
    total = sum(item['quantity'] * item['price'] for item in cart_items)
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>My Cart</h1>
            <ul>
                {% for item in cart_items %}
                <li>{{ item.name }} x {{ item.quantity }} - ${{ item.quantity * item.price }}</li>
                <form action="/cart/remove/{{ item.cart_item_id }}" method="post">
                    <button type="submit">Remove</button>
                </form>
                {% endfor %}
            </ul>
            <p>Total: ${{ total }}</p>
            <form action="/cart/checkout" method="post">
                <button type="submit">Checkout</button>
            </form>
        </body>
        </html>
    ''', cart_items=cart_items, total=total)

@app.post("/cart/remove/{cart_item_id}")
async def remove_from_cart(request: Request, cart_item_id: int):
    member_id = request.session.get("member_id")
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    conn.execute('DELETE FROM cart_items WHERE cart_item_id = ?', (cart_item_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body>Item removed from cart</body></html>')

@app.post("/cart/checkout")
async def checkout(request: Request):
    member_id = request.session.get("member_id")
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cart_items = conn.execute('SELECT * FROM cart_items WHERE owner_id = ?', (member_id,)).fetchall()
    total = sum(item['quantity'] * item['price'] for item in cart_items)
    order_id = conn.execute('INSERT INTO orders (buyer_id, total_amount, status) VALUES (?, ?, ?)', (member_id, total, 'PLACED')).lastrowid
    for item in cart_items:
        conn.execute('INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)', (order_id, item['product_id'], item['quantity'], item['price']))
    conn.execute('DELETE FROM cart_items WHERE owner_id = ?', (member_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body>Order placed</body></html>')

@app.get("/orders")
async def list_orders(request: Request):
    member_id = request.session.get("member_id")
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    orders = conn.execute('SELECT * FROM orders WHERE buyer_id = ? OR is_admin = 1 ORDER BY created_at DESC', (member_id,)).fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>My Orders</h1>
            <ul>
                {% for order in orders %}
                <li><a href="/orders/{{ order.order_id }}">{{ order.order_id }} - ${{ order.total_amount }} - {{ order.status }}</a></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', orders=orders)

@app.get("/orders/{order_id}")
async def view_order(request: Request, order_id: int):
    member_id = request.session.get("member_id")
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    order = conn.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,)).fetchone()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order['buyer_id'] != member_id and not order['is_admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    order_items = conn.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,)).fetchall()
    total = sum(item['quantity'] * item['unit_price'] for item in order_items)
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>Order {{ order_id }}</h1>
            <p>Total: ${{ total }}</p>
            <p>Status: {{ order.status }}</p>
            <ul>
                {% for item in order_items %}
                <li>{{ item.name }} x {{ item.quantity }} - ${{ item.quantity * item.unit_price }}</li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', order=order, order_items=order_items, total=total)

@app.get("/admin/products/create")
async def create_product_form(request: Request):
    member_id = request.session.get("member_id")
    if not member_id or not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return render_template_string('''
        <html>
        <body>
            <h1>Create Product</h1>
            <form action="/admin/products/create" method="post">
                <label for="name">Name:</label>
                <input type="text" id="name" name="name" required>
                <label for="description">Description:</label>
                <textarea id="description" name="description" required></textarea>
                <label for="price">Price:</label>
                <input type="number" id="price" name="price" step="0.01" required>
                <label for="stock">Stock:</label>
                <input type="number" id="stock" name="stock" required>
                <button type="submit">Create</button>
            </form>
        </body>
        </html>
    ''')

@app.post("/admin/products/create")
async def create_product(request: Request, name: str = Form(...), description: str = Form(...), price: float = Form(...), stock: int = Form(...)):
    member_id = request.session.get("member_id")
    if not member_id or not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    conn = get_db()
    conn.execute('INSERT INTO products (name, description, price, stock) VALUES (?, ?, ?, ?)', (name, description, price, stock))
    conn.commit()
    conn.close()
    return render_template_string('<html><body>Product created</body></html>')

@app.get("/admin/products/edit/{product_id}")
async def edit_product_form(request: Request, product_id: int):
    member_id = request.session.get("member_id")
    if not member_id or not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE product_id = ?', (product_id,)).fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>Edit Product</h1>
            <form action="/admin/products/edit/{{ product_id }}" method="post">
                <label for="name">Name:</label>
                <input type="text" id="name" name="name" value="{{ product.name }}" required>
                <label for="description">Description:</label>
                <textarea id="description" name="description">{{ product.description }}</textarea>
                <label for="price">Price:</label>
                <input type="number" id="price" name="price" value="{{ product.price }}" step="0.01" required>
                <label for="stock">Stock:</label>
                <input type="number" id="stock" name="stock" value="{{ product.stock }}" required>
                <button type="submit">Update</button>
            </form>
        </body>
        </html>
    ''', product=product)

@app.post("/admin/products/edit/{product_id}")
async def edit_product(request: Request, product_id: int, name: str = Form(...), description: str = Form(...), price: float = Form(...), stock: int = Form(...)):
    member_id = request.session.get("member_id")
    if not member_id or not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    conn = get_db()
    conn.execute('UPDATE products SET name = ?, description = ?, price = ?, stock = ? WHERE product_id = ?', (name, description, price, stock, product_id))
    conn.commit()
    conn.close()
    return render_template_string('<html><body>Product updated</body></html>')

@app.post("/admin/products/delete/{product_id}")
async def delete_product(request: Request, product_id: int):
    member_id = request.session.get("member_id")
    if not member_id or not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    conn = get_db()
    conn.execute('UPDATE products SET is_deleted = 1 WHERE product_id = ?', (product_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body>Product deleted</body></html>')

@app.get("/admin/orders")
async def list_orders_admin(request: Request):
    member_id = request.session.get("member_id")
    if not member_id or not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    conn = get_db()
    orders = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>Orders</h1>
            <ul>
                {% for order in orders %}
                <li><a href="/orders/{{ order.order_id }}">{{ order.order_id }} - ${{ order.total_amount }} - {{ order.status }}</a></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', orders=orders)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)