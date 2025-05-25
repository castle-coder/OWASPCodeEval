from fastapi import FastAPI, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.exceptions import RequestValidationError
import sqlite3
import hashlib
import secrets
import hmac
import re

app = FastAPI()

# Middleware
app.add_middleware(
    SessionMiddleware,
    secret_key="your-secret-key",
    max_age=3600,
    same_site="lax",
)

# -------- 예외 핸들러 --------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Invalid member ID"},
    )

# -------- 보안 해시 함수 정의 --------
def hash_password(password: str, salt: str = None) -> str:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${hashed.hex()}"

def verify_password(input_password: str, stored_hash: str) -> bool:
    try:
        salt, hashed = stored_hash.split('$')
        test_hash = hashlib.pbkdf2_hmac("sha256", input_password.encode(), salt.encode(), 100_000).hex()
        return hmac.compare_digest(test_hash, hashed)
    except Exception:
        return False

# -------- 기타 헬퍼 함수 --------
def sanitize_input(text):
    return re.sub(r'<.*?>', '', text)

def get_user_by_id(user_id: int):
    cursor.execute("SELECT * FROM users WHERE user_id = ? AND is_deleted = 0", (user_id,))
    return cursor.fetchone()

def get_user_by_email(email: str):
    cursor.execute("SELECT * FROM users WHERE email = ? AND is_deleted = 0", (email,))
    return cursor.fetchone()

# -------- 데이터베이스 초기화 --------
DATABASE_NAME = 'mock_db.sqlite3'
conn = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0
        )
    """)
    existing = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing == 0:
        hashed_pw = hash_password("password123")
        cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)",
                       ('user', 'user@example.com', hashed_pw, 0, 0))
        cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)",
                       ('admin', 'admin@example.com', hashed_pw, 1, 0))
    conn.commit()

init_db()

# -------- 라우트 핸들러 --------

@app.get("/login/{member_id}")
def login(member_id: int, request: Request):
    user = get_user_by_id(member_id)
    if not user:
        raise HTTPException(status_code=403, detail="Authentication failed")
    request.session["member_id"] = member_id
    request.session["is_admin"] = user[4]
    return {"message": "Logged in successfully"}

@app.post("/members/register")
def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    try:
        username = sanitize_input(username)
        email = sanitize_input(email)
        hashed_password = hash_password(password)
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, hashed_password))
        conn.commit()
        return {"message": "Registration successful"}
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error during registration")

@app.get("/members/{member_id}", response_class=HTMLResponse)
def view_profile(member_id: int, request: Request):
    if "member_id" not in request.session:
        raise HTTPException(status_code=403, detail="Not logged in")
    if request.session["member_id"] != member_id:
        raise HTTPException(status_code=403, detail="Access denied")
    user = get_user_by_id(member_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return f"""
        <html>
            <head><title>Profile</title></head>
            <body>
                <h1>Profile</h1>
                <p>Username: {user[1]}</p>
                <p>Email: {user[2]}</p>
            </body>
        </html>
    """

@app.post("/members/update", response_class=HTMLResponse)
def update_profile(request: Request, username: str = Form(...), email: str = Form(...)):
    if "member_id" not in request.session:
        raise HTTPException(status_code=403, detail="Not logged in")

    user_id = request.session["member_id"]
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=403, detail="User not found")

    username = sanitize_input(username)
    email = sanitize_input(email)

    cursor.execute("UPDATE users SET username = ?, email = ? WHERE user_id = ?", (username, email, user_id))
    conn.commit()
    return {"message": "Profile updated successfully"}

@app.post("/members/delete", response_class=HTMLResponse)
def delete_account(request: Request):
    if "member_id" not in request.session:
        raise HTTPException(status_code=403, detail="Not logged in")
    user_id = request.session["member_id"]
    cursor.execute("UPDATE users SET is_deleted = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    request.session.clear()
    return {"message": "Account deleted successfully"}

@app.post("/admin/deactivate_member/{member_id}", response_class=HTMLResponse)
def admin_deactivate_member(member_id: int, request: Request):
    if "is_admin" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    cursor.execute("UPDATE users SET is_deleted = 1 WHERE user_id = ?", (member_id,))
    conn.commit()
    return {"message": "Member deactivated successfully"}

@app.get("/members", response_class=HTMLResponse)
def list_members(request: Request):
    cursor.execute("SELECT * FROM users WHERE is_deleted = 0")
    members = cursor.fetchall()
    return f"""
        <html>
            <head><title>Members</title></head>
            <body>
                <h1>Active Members</h1>
                <ul>
                    {''.join([f'<li>{sanitize_input(member[1])} - {sanitize_input(member[2])}</li>' for member in members])}
                </ul>
            </body>
        </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)