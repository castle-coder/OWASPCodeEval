from fastapi import FastAPI, Request, Form, HTTPException, Depends
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse
from jinja2 import Template
import sqlite3
import random
from datetime import datetime, timedelta
import hashlib

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
    hashed_password = hashlib.sha256("password".encode()).hexdigest()
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, email_verified)
        VALUES (?, ?, ?, ?, ?)
    ''', ('user', 'user@example.com', hashed_password, 0, 0))
    hashed_password = hashlib.sha256("admin_password".encode()).hexdigest()
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, email_verified)
        VALUES (?, ?, ?, ?, ?)
    ''', ('admin', 'admin@example.com', hashed_password, 1, 1))
    conn.commit()
    conn.close()

@app.get("/register")
async def register_form(request: Request):
    html = '''
        <form method="post" action="/register">
            <input type="text" name="username" placeholder="Username" required>
            <input type="email" name="email" placeholder="Email" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Register</button>
        </form>
    '''
    return render_template_string(html)

@app.post("/register")
async def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    conn = get_db()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    verification_code = str(random.randint(100000, 999999))
    verification_expires = datetime.now() + timedelta(minutes=10)
    conn.execute('''
        INSERT INTO users (username, email, password, verification_code, verification_expires)
        VALUES (?, ?, ?, ?, ?)
    ''', (username, email, hashed_password, verification_code, verification_expires))
    user_id = conn.lastrowid
    conn.commit()
    conn.close()
    return render_template_string('<a href="/auth/send/{}">Send Verification Email</a>'.format(user_id))

@app.get("/auth/send/{user_id}")
async def send_verification_email(request: Request, user_id: int):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    if user and not user['email_verified']:
        verification_code = str(random.randint(100000, 999999))
        verification_expires = datetime.now() + timedelta(minutes=10)
        conn.execute('''
            UPDATE users SET verification_code = ?, verification_expires = ? WHERE user_id = ?
        ''', (verification_code, verification_expires, user_id))
        conn.commit()
        conn.close()
        return render_template_string('<p>Verification code: {}</p>'.format(verification_code))
    else:
        conn.close()
        return render_template_string('<p>Email already verified or user not found.</p>')

@app.get("/auth/verify")
async def verify_form(request: Request):
    html = '''
        <form method="post" action="/auth/verify">
            <input type="text" name="user_id" placeholder="User ID" required>
            <input type="text" name="code" placeholder="Verification Code" required>
            <button type="submit">Verify</button>
        </form>
    '''
    return render_template_string(html)

@app.post("/auth/verify")
async def verify(request: Request, user_id: str = Form(...), code: str = Form(...)):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    if user and user['email_verified'] == 0 and user['verification_code'] == code and user['verification_expires'] > datetime.now():
        conn.execute('''
            UPDATE users SET email_verified = 1, verification_code = NULL, verification_expires = NULL WHERE user_id = ?
        ''', (user_id,))
        conn.commit()
        conn.close()
        return render_template_string('<p>Email verified successfully.</p>')
    else:
        conn.close()
        return render_template_string('<p>Invalid code or code expired.</p>')

@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE user_id = ? AND email_verified = 1', (user_id,)).fetchone()
    if user:
        request.session['user_id'] = user_id
        request.session['is_admin'] = user['is_admin']
        conn.close()
        return render_template_string('<p>Logged in successfully.</p>')
    else:
        conn.close()
        return render_template_string('<p>Invalid user or email not verified.</p>')

@app.get("/admin/unverified")
async def admin_unverified(request: Request):
    if 'user_id' not in request.session or not request.session['is_admin']:
        return render_template_string('<p>Admin access required.</p>')
    conn = get_db()
    users = conn.execute('SELECT * FROM users WHERE email_verified = 0').fetchall()
    conn.close()
    html = '<ul>'
    for user in users:
        html += '<li>{}</li>'.format(user['username'])
    html += '</ul>'
    return render_template_string(html)

@app.post("/admin/force_verify/{user_id}")
async def admin_force_verify(request: Request, user_id: int):
    if 'user_id' not in request.session or not request.session['is_admin']:
        return render_template_string('<p>Admin access required.</p>')
    conn = get_db()
    conn.execute('''
        UPDATE users SET email_verified = 1 WHERE user_id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()
    return render_template_string('<p>User verified successfully.</p>')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)