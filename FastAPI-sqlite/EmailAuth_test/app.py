from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime, timedelta
import sqlite3
from jinja2 import Template
import random

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

def get_db():
    conn = sqlite3.connect("mock_db.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
def startup():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
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
    cursor.execute('''
        INSERT INTO users (username, email, password, is_admin, email_verified)
        SELECT 'user', 'user@example.com', '<hashed>', 0, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'user@example.com')
    ''')
    cursor.execute('''
        INSERT INTO users (username, email, password, is_admin, email_verified)
        SELECT 'admin', 'admin@example.com', '<hashed>', 1, 1
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'admin@example.com')
    ''')
    conn.commit()
    conn.close()

@app.get("/register")
async def register_form(request: Request):
    html = '''
        <form method="post" action="/register">
            Username: <input type="text" name="username"><br>
            Email: <input type="email" name="email"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Register">
        </form>
    '''
    return render_template_string(html)

@app.post("/register")
async def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM users WHERE email = ?', (email,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Email already registered")
    verification_code = str(random.randint(100000, 999999))
    verification_expires = datetime.now() + timedelta(minutes=10)
    cursor.execute('''
        INSERT INTO users (username, email, password, verification_code, verification_expires)
        VALUES (?, ?, ?, ?, ?)
    ''', (username, email, password, verification_code, verification_expires))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return render_template_string('<a href="/auth/send/{}">Send Verification Email</a>'.format(user_id))

@app.get("/auth/send/{user_id}")
async def send_verification_email(request: Request, user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user['email_verified']:
        raise HTTPException(status_code=400, detail="Email already verified")
    verification_code = str(random.randint(100000, 999999))
    verification_expires = datetime.now() + timedelta(minutes=10)
    cursor.execute('''
        UPDATE users SET verification_code = ?, verification_expires = ? WHERE user_id = ?
    ''', (verification_code, verification_expires, user_id))
    conn.commit()
    conn.close()
    return render_template_string('<p>Verification code sent: {}</p>'.format(verification_code))

@app.get("/auth/verify")
async def verify_form(request: Request):
    html = '''
        <form method="post" action="/auth/verify">
            User ID: <input type="text" name="user_id"><br>
            Code: <input type="text" name="code"><br>
            <input type="submit" value="Verify">
        </form>
    '''
    return render_template_string(html)

@app.post("/auth/verify")
async def verify(request: Request, user_id: str = Form(...), code: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user['email_verified']:
        raise HTTPException(status_code=400, detail="Email already verified")
    if user['verification_code'] != code or user['verification_expires'] < datetime.now():
        return render_template_string('<p>Invalid code or expired</p>')
    cursor.execute('''
        UPDATE users SET email_verified = 1, verification_code = NULL, verification_expires = NULL WHERE user_id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()
    return render_template_string('<p>Email verified successfully</p>')

@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user['email_verified']:
        raise HTTPException(status_code=400, detail="Email not verified")
    request.session['user_id'] = user_id
    request.session['is_admin'] = user['is_admin']
    return render_template_string('<p>Logged in as user {}</p>'.format(user_id))

@app.get("/admin/unverified")
async def admin_unverified(request: Request):
    if 'user_id' not in request.session or not request.session['is_admin']:
        raise HTTPException(status_code=403, detail="Admin access required")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, email FROM users WHERE email_verified = 0')
    users = cursor.fetchall()
    html = '<ul>'
    for user in users:
        html += '<li>User ID: {}, Username: {}, Email: {}'.format(user['user_id'], user['username'], user['email'])
    html += '</ul>'
    return render_template_string(html)

@app.post("/admin/force_verify/{user_id}")
async def admin_force_verify(request: Request, user_id: int):
    if 'user_id' not in request.session or not request.session['is_admin']:
        raise HTTPException(status_code=403, detail="Admin access required")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET email_verified = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return render_template_string('<p>User {} verified</p>'.format(user_id))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)