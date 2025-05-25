from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlite3 import connect, Cursor
from typing import List, Dict, Optional

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

DATABASE = 'mock_db.sqlite3'

def get_db():
    connection = connect(DATABASE)
    yield connection
    connection.close()

def get_user(request: Request):
    return request.session.get('user_id')

@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    request.session['user_id'] = user_id
    request.session['is_admin'] = False
    return HTMLResponse(content=templates.TemplateResponse("index.html", {"request": request}))

@app.get("/products")
async def products(request: Request):
    connection = get_db()
    cursor: Cursor = connection.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    return HTMLResponse(content=templates.TemplateResponse("products.html", {"request": request, "products": products}))

@app.get("/products/{product_id}")
async def product(request: Request, product_id: int):
    connection = get_db()
    cursor: Cursor = connection.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    return HTMLResponse(content=templates.TemplateResponse("product.html", {"request": request, "product": product}))

@app.post("/cart/add/{product_id}")
async def add_to_cart(request: Request, product_id: int, quantity: int = Form(...)):
    user_id = get_user(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    request.session.setdefault('cart', []).append({'product_id': product_id, 'quantity': quantity})
    return {"message": "Product added to cart"}

@app.get("/cart")
async def cart(request: Request):
    user_id = get_user(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    cart = request.session.get('cart', [])
    connection = get_db()
    cursor: Cursor = connection.cursor()
    cursor.execute("SELECT * FROM products WHERE id IN ({})".format(','.join('?' for _ in cart)))
    products = cursor.fetchall()
    cart_items = [{'name': p[1], 'quantity': c['quantity'], 'price': p[3], 'subtotal': p[3] * c['quantity']} for p, c in zip(products, cart)]
    total = sum(item['subtotal'] for item in cart_items)
    return HTMLResponse(content=templates.TemplateResponse("cart.html", {"request": request, "cart_items": cart_items, "total": total}))

@app.post("/cart/checkout")
async def checkout(request: Request):
    user_id = get_user(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    cart = request.session.get('cart', [])
    connection = get_db()
    cursor: Cursor = connection.cursor()
    cursor.execute("SELECT * FROM products WHERE id IN ({})".format(','.join('?' for _ in cart)))
    products = cursor.fetchall()
    total_amount = sum(p[3] * c['quantity'] for p, c in zip(products, cart))
    cursor.execute("INSERT INTO orders (user_id, total_amount) VALUES (?, ?)", (user_id, total_amount))
    order_id = cursor.lastrowid
    for p, c in zip(products, cart):
        cursor.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)", (order_id, p[0], c['quantity'], p[3]))
    connection.commit()
    request.session.pop('cart', None)
    return {"message": "Checkout successful"}

@app.get("/orders")
async def orders(request: Request):
    user_id = get_user(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    connection = get_db()
    cursor: Cursor = connection.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = ?", (user_id,))
    orders = cursor.fetchall()
    return HTMLResponse(content=templates.TemplateResponse("orders.html", {"request": request, "orders": orders}))

@app.get("/orders/{order_id}")
async def order_details(request: Request, order_id: int):
    user_id = get_user(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    connection = get_db()
    cursor: Cursor = connection.cursor()
    cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    order = cursor.fetchone()
    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    order_items = cursor.fetchall()
    return HTMLResponse(content=templates.TemplateResponse("order_details.html", {"request": request, "order": order, "order_items": order_items}))

@app.post("/admin/product")
async def admin_add_product(request: Request, name: str = Form(...), description: str = Form(...), price: float = Form(...)):
    user_id = get_user(request)
    if not user_id or not request.session.get('is_admin'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    connection = get_db()
    cursor: Cursor = connection.cursor()
    cursor.execute("INSERT INTO products (name, description, price) VALUES (?, ?, ?)", (name, description, price))
    connection.commit()
    return {"message": "Product added"}

@app.get("/admin/product/edit/{product_id}")
async def admin_edit_product(request: Request, product_id: int):
    user_id = get_user(request)
    if not user_id or not request.session.get('is_admin'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    connection = get_db()
    cursor: Cursor = connection.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    return HTMLResponse(content=templates.TemplateResponse("edit_product.html", {"request": request, "product": product}))

@app.post("/admin/product/edit/{product_id}")
async def admin_update_product(request: Request, product_id: int, name: str = Form(...), description: str = Form(...), price: float = Form(...)):
    user_id = get_user(request)
    if not user_id or not request.session.get('is_admin'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    connection = get_db()
    cursor: Cursor = connection.cursor()
    cursor.execute("UPDATE products SET name = ?, description = ?, price = ? WHERE id = ?", (name, description, price, product_id))
    connection.commit()
    return {"message": "Product updated"}

@app.post("/admin/product/delete/{product_id}")
async def admin_delete_product(request: Request, product_id: int):
    user_id = get_user(request)
    if not user_id or not request.session.get('is_admin'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    connection = get_db()
    cursor: Cursor = connection.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    connection.commit()
    return {"message": "Product deleted"}

def main():
    connection = connect(DATABASE)
    cursor: Cursor = connection.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, is_admin BOOLEAN)")
    cursor.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, price REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("CREATE TABLE IF NOT EXISTS orders (order_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, total_amount REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(user_id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS order_items (item_id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, product_id INTEGER, quantity INTEGER, price REAL, FOREIGN KEY (order_id) REFERENCES orders(order_id), FOREIGN KEY (product_id) REFERENCES products(id))")
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    cursor.execute("INSERT INTO products (name, description, price) VALUES (?, ?, ?)", ('Sample Item', 'A sample product.', 9.99))
    connection.commit()
    connection.close()

if __name__ == "__main__":
    main()