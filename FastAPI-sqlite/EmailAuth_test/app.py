from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.status import HTTP_401_UNAUTHORIZED
from datetime import datetime, timedelta
import sqlite3
import secrets
import hashlib

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

DATABASE = 'mock_db.sqlite3'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
def startup():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            is_verified BOOLEAN
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS email_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.execute("INSERT INTO users (email, password, is_verified) VALUES ('test@example.com', 'hashed_pw', 0)")
    conn.commit()
    conn.close()

@app.post("/register")
async def register(email: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn.execute("INSERT INTO users (email, password, is_verified) VALUES (?, ?, ?)", (email, hashed_password, False))
    conn.commit()
    conn.close()
    return {"message": "Registration successful. Please check your email for verification."}

@app.post("/send-verification/{user_id}")
async def send_verification(user_id: int):
    conn = get_db_connection()
    token = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    conn.execute("INSERT INTO email_tokens (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
    conn.commit()
    conn.close()
    # Simulate sending email
    verification_url = f"http://localhost:8000/verify/{token}"
    body = Template("""
    <h1>Verify Your Email</h1>
    <p>Please click <a href="{{ url }}">here</a> to verify your address.</p>
    """).render(url=verification_url)
    send_email(email, "Email Verification", body)
    return {"message": "Verification email sent."}

@app.get("/verify/{token}")
async def verify(token: str):
    conn = get_db_connection()
    token_info = conn.execute("SELECT * FROM email_tokens WHERE token = ?", (token,)).fetchone()
    if not token_info or token_info['expires_at'] < datetime.utcnow():
        conn.close()
        return {"message": "Invalid or expired token."}
    user_id = token_info['user_id']
    conn.execute("UPDATE users SET is_verified = ? WHERE id = ?", (True, user_id))
    conn.execute("DELETE FROM email_tokens WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    html = Template("""
    <h1>Email Verified</h1>
    <p>Your email has been successfully verified.</p>
    """).render()
    return HTMLResponse(html)

@app.post("/resend-verification/{user_id}")
async def resend_verification(user_id: int):
    conn = get_db_connection()
    token = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    conn.execute("INSERT INTO email_tokens (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
    conn.commit()
    conn.close()
    # Simulate sending email
    verification_url = f"http://localhost:8000/verify/{token}"
    body = Template("""
    <h1>Verify Your Email</h1>
    <p>Please click <a href="{{ url }}">here</a> to verify your address.</p>
    """).render(url=verification_url)
    send_email(email, "Email Verification", body)
    return {"message": "Verification email resent."}

@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user or user['password'] != hashlib.sha256(password.encode()).hexdigest() or not user['is_verified']:
        conn.close()
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid credentials or email not verified.")
    request.session['user_id'] = user['id']
    request.session['is_verified'] = user['is_verified']
    conn.close()
    return {"message": "Login successful."}

@app.get("/profile")
async def profile(request: Request):
    user_id = request.session.get('user_id')
    is_verified = request.session.get('is_verified')
    if not user_id or not is_verified:
        return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    html = Template("""
    <h1>Profile</h1>
    <p>Email: {{ user.email }}</p>
    <p>Verified: {{ user.is_verified }}</p>
    """).render(user=user)
    return HTMLResponse(html)

def send_email(email, subject, body):
    # Implement email sending logic here
    pass