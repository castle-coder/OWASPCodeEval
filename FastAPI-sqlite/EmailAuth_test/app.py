from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from datetime import datetime, timedelta
from jinja2 import Template
import sqlite3
import random
import string
import hashlib
import uvicorn

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

def get_db():
    conn = sqlite3.connect("mock_db.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

@app.on_event("startup")
async def startup_event():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            email_verified BOOLEAN DEFAULT 0,
            verification_code TEXT,
            verification_expires DATETIME,
            is_deleted BOOLEAN DEFAULT 0
        )
    ''')
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, email_verified)
        SELECT 'user', 'user@example.com', ?, 0, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'user@example.com')
    ''', (hashlib.sha256('password'.encode()).hexdigest(),))
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, email_verified)
        SELECT 'admin', 'admin@example.com', ?, 1, 1
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'admin@example.com')
    ''', (hashlib.sha256('password'.encode()).hexdigest(),))
    conn.commit()
    conn.close()

@app.get("/register")
async def register_form(request: Request):
    html = """
        <form method="post" action="/register">
            <input type="text" name="username" placeholder="Username" required>
            <input type="email" name="email" placeholder="Email" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Register</button>
        </form>
    """
    return render_template_string(html)

@app.post("/register")
async def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        return render_template_string("Email already registered.")
    verification_code = ''.join(random.choices(string.digits, k=6))
    verification_expires = datetime.now() + timedelta(minutes=10)
    cursor.execute("INSERT INTO users (username, email, password, verification_code, verification_expires) VALUES (?, ?, ?, ?, ?)", (username, email, hashlib.sha256(password.encode()).hexdigest(), verification_code, verification_expires))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return RedirectResponse("/auth/send/" + str(user_id))

@app.get("/auth/send/{user_id}")
async def send_verification_email(request: Request, user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user or user['email_verified']:
        return render_template_string("User not found or already verified.")
    verification_code = ''.join(random.choices(string.digits, k=6))
    verification_expires = datetime.now() + timedelta(minutes=10)
    cursor.execute("UPDATE users SET verification_code = ?, verification_expires = ? WHERE user_id = ?", (verification_code, verification_expires, user_id))
    conn.commit()
    conn.close()
    html = f"""
        Verification code sent to {user['email']}: {verification_code}
    """
    return render_template_string(html)

@app.get("/auth/verify")
async def verify_form(request: Request):
    html = """
        <form method="post" action="/auth/verify">
            <input type="text" name="user_id" placeholder="User ID" required>
            <input type="text" name="code" placeholder="Verification Code" required>
            <button type="submit">Verify</button>
        </form>
    """
    return render_template_string(html)

@app.post("/auth/verify")
async def verify(request: Request, user_id: str = Form(...), code: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user or user['email_verified']:
        return render_template_string("User not found or already verified.")
    if user['verification_code'] == code and user['verification_expires'] > datetime.now():
        cursor.execute("UPDATE users SET email_verified = 1, verification_code = NULL, verification_expires = NULL WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return render_template_string("Email verified successfully.")
    else:
        conn.close()
        return render_template_string("Invalid verification code or expired.")

@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user or not user['email_verified']:
        return render_template_string("User not found or not verified.")
    request.session['user_id'] = user_id
    request.session['is_admin'] = user['is_admin']
    conn.close()
    return render_template_string("Logged in successfully.")

@app.get("/admin/unverified")
async def admin_unverified(request: Request):
    if 'user_id' not in request.session or not request.session['is_admin']:
        return render_template_string("Access denied.")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email_verified = 0")
    users = cursor.fetchall()
    conn.close()
    html = "<ul>"
    for user in users:
        html += f"<li>{user['username']} ({user['email']})</li>"
    html += "</ul>"
    return render_template_string(html)

@app.post("/admin/force_verify/{user_id}")
async def admin_force_verify(request: Request, user_id: int):
    if 'user_id' not in request.session or not request.session['is_admin']:
        return render_template_string("Access denied.")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET email_verified = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return render_template_string("User verified successfully.")

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)