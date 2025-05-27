from flask import Flask, request, session, render_template_string, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def create_tables_and_insert_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            is_admin BOOLEAN
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            price REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            total_amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            price REAL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS report (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    cursor.execute("INSERT INTO products (name, description, price) VALUES (?, ?, ?)", ('Sample Item', 'A sample product.', 9.99))
    conn.commit()
    conn.close()

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = False
    return redirect(url_for('products'))

@app.route('/products')
def products():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    return render_template_string('''
        <h1>Products</h1>
        <ul>
            {% for product in products %}
            <li><a href="/products/{{ product.id }}">{{ product.name }}</a></li>
            {% endfor %}
        </ul>
    ''', products=products)

@app.route('/products/<product_id>')
def product(product_id):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    return render_template_string('''
        <h1>{{ product.name }}</h1>
        <p>{{ product.description }}</p>
        <p>Price: ${{ product.price }}</p>
        <p>Created at: {{ product.created_at }}</p>
    ''', product=product)

@app.route('/cart/add/<product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))
    quantity = int(request.form['quantity'])
    if 'cart' not in session:
        session['cart'] = []
    session['cart'].append({'product_id': product_id, 'quantity': quantity})
    return redirect(url_for('products'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))
    cart = session.get('cart', [])
    total = sum(int(item['quantity']) * get_product_price(item['product_id']) for item in cart)
    return render_template_string('''
        <h1>Cart</h1>
        <ul>
            {% for item in cart %}
            <li>{{ get_product_name(item['product_id']) }} x {{ item['quantity'] }} - ${{ item['quantity'] * get_product_price(item['product_id']) }}</li>
            {% endfor %}
        </ul>
        <p>Total: ${{ total }}</p>
    ''', cart=cart, get_product_name=get_product_name, get_product_price=get_product_price)

@app.route('/cart/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))
    user_id = session['user_id']
    cart = session.get('cart', [])
    total = sum(int(item['quantity']) * get_product_price(item['product_id']) for item in cart)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (user_id, total_amount) VALUES (?, ?)', (user_id, total))
    order_id = cursor.lastrowid
    for item in cart:
        cursor.execute('INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)', (order_id, item['product_id'], item['quantity'], get_product_price(item['product_id'])))
    conn.commit()
    session.pop('cart', None)
    conn.close()
    return redirect(url_for('orders'))

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))
    user_id = session['user_id']
    conn = get_db_connection()
    orders = conn.execute('SELECT * FROM orders WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return render_template_string('''
        <h1>Order History</h1>
        <ul>
            {% for order in orders %}
            <li><a href="/orders/{{ order.order_id }}">{{ order.order_id }}</a> - ${{ order.total_amount }} - {{ order.created_at }}</li>
            {% endfor %}
        </ul>
    ''', orders=orders)

@app.route('/orders/<order_id>')
def order_details(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))
    conn = get_db_connection()
    order = conn.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,)).fetchone()
    order_items = conn.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,)).fetchall()
    conn.close()
    return render_template_string('''
        <h1>Order Details</h1>
        <p>Order ID: {{ order.order_id }}</p>
        <p>Total: ${{ order.total_amount }}</p>
        <p>Created at: {{ order.created_at }}</p>
        <ul>
            {% for item in order_items %}
            <li>{{ get_product_name(item['product_id']) }} x {{ item['quantity'] }} - ${{ item['quantity'] * item['price'] }}</li>
            {% endfor %}
        </ul>
    ''', order=order, order_items=order_items, get_product_name=get_product_name)

@app.route('/admin/product', methods=['POST'])
def admin_add_product():
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('login', user_id=1))
    name = request.form['name']
    description = request.form['description']
    price = float(request.form['price'])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO products (name, description, price) VALUES (?, ?, ?)', (name, description, price))
    conn.commit()
    conn.close()
    return redirect(url_for('products'))

@app.route('/admin/product/edit/<product_id>', methods=['POST'])
def admin_edit_product(product_id):
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('login', user_id=1))
    name = request.form['name']
    description = request.form['description']
    price = float(request.form['price'])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET name = ?, description = ?, price = ? WHERE id = ?', (name, description, price, product_id))
    conn.commit()
    conn.close()
    return redirect(url_for('products'))

@app.route('/admin/product/delete/<product_id>', methods=['POST'])
def admin_delete_product(product_id):
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('login', user_id=1))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('products'))

@app.route('/report', methods=['POST'])
def report():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))
    user_id = session['user_id']
    content = request.form['content']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO report (user_id, content) VALUES (?, ?)', (user_id, content))
    conn.commit()
    conn.close()
    return redirect(url_for('products'))

def get_product_name(product_id):
    conn = get_db_connection()
    product = conn.execute('SELECT name FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    return product['name']

def get_product_price(product_id):
    conn = get_db_connection()
    product = conn.execute('SELECT price FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    return product['price']

if __name__ == '__main__':
    app.run(debug=True)