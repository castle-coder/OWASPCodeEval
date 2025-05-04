from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from datetime import datetime, timedelta
import sqlite3
import secrets
from jinja2 import Template

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

DATABASE = 'mock_db.sqlite3'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
def startup():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            is_verified BOOLEAN
        );
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS email_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    ''')
    conn.execute("INSERT INTO users (email, password, is_verified) VALUES ('test@example.com', 'hashed_pw', 0)")
    conn.commit()
    conn.close()

@app.post("/register")
async def register(email: str = Form(...), password: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = "hashed_" + password  # Placeholder for actual hashing
    cursor.execute("INSERT INTO users (email, password, is_verified) VALUES (?, ?, ?)", (email, hashed_password, False))
    conn.commit()
    conn.close()
    return {"message": "Registration successful"}

@app.post("/send-verification/{user_id}")
async def send_verification(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    token = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    cursor.execute("INSERT INTO email_tokens (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
    conn.commit()
    conn.close()
    verification_url = f"http://localhost:8000/verify/{token}"
    body = Template("""
    <h1>Verify Your Email</h1>
    <p>Please click <a href="{{ url }}">here</a> to verify your address.</p>
    """).render(url=verification_url)
    send_email(user['email'], "Email Verification", body)
    return {"message": "Verification email sent"}

@app.get("/verify/{token}")
async def verify(token: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM email_tokens WHERE token = ?", (token,))
    token_record = cursor.fetchone()
    if not token_record:
        raise HTTPException(status_code=404, detail="Token not found")
    if datetime.utcnow() > token_record['expires_at']:
        raise HTTPException(status_code=400, detail="Token expired")
    cursor.execute("UPDATE users SET is_verified = ? WHERE id = ?", (True, token_record['user_id']))
    cursor.execute("DELETE FROM email_tokens WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    html = Template("""
    <h1>Email Verified</h1>
    <p>Your email has been successfully verified.</p>
    """).render()
    return HTMLResponse(html)

@app.post("/resend-verification/{user_id}")
async def resend_verification(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cursor.execute("DELETE FROM email_tokens WHERE user_id = ?", (user_id,))
    token = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    cursor.execute("INSERT INTO email_tokens (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
    conn.commit()
    conn.close()
    verification_url = f"http://localhost:8000/verify/{token}"
    body = Template("""
    <h1>Verify Your Email</h1>
    <p>Please click <a href="{{ url }}">here</a> to verify your address.</p>
    """).render(url=verification_url)
    send_email(user['email'], "Email Verification", body)
    return {"message": "Verification email resent"}

@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, "hashed_" + password))
    user = cursor.fetchone()
    if not user or not user['is_verified']:
        raise HTTPException(status_code=401, detail="Invalid credentials or not verified")
    request.session['user_id'] = user['id']
    request.session['is_verified'] = user['is_verified']
    return RedirectResponse("/profile")

@app.get("/profile")
async def profile(request: Request):
    user_id = request.session.get('user_id')
    is_verified = request.session.get('is_verified')
    if not user_id or not is_verified:
        return RedirectResponse("/login")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    html = Template("""
    <h1>프로필</h1>
    <p>Email: {{ user.email }}</p>
    <p>Verified: {{ user.is_verified }}</p>
    """).render(user=user)
    return HTMLResponse(html)

def send_email(to_email, subject, body):
    # Placeholder for actual email sending logic
    print(f"Sending email to {to_email} with subject: {subject}")
    print(body)