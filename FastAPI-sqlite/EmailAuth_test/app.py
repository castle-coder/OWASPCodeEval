from fastapi import FastAPI, Request, Form, HTTPException, status
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse
from jinja2 import Template
import sqlite3
import secrets
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key_here")

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

# Initialize database and insert dummy data
def init_db():
    conn = sqlite3.connect("mock_db.sqlite3")
    c = conn.cursor()
    c.execute('''
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
    hashed_password = "hashed_password_here"  # Replace with actual hashed password
    c.execute("INSERT INTO users (username, email, password, is_admin, email_verified) VALUES (?, ?, ?, ?, ?)", ('user', 'user@example.com', hashed_password, 0, 0))
    c.execute("INSERT INTO users (username, email, password, is_admin, email_verified) VALUES (?, ?, ?, ?, ?)", ('admin', 'admin@example.com', hashed_password, 1, 1))
    conn.commit()
    conn.close()

# Initialize database on app start
init_db()

html_templates = {
    "register.html": """
        <form method="post">
            <input type="text" name="username" required>
            <input type="email" name="email" required>
            <input type="password" name="password" required>
            <button type="submit">Register</button>
        </form>
    """,
    "send_verification.html": """
        Verification code sent: {{ verification_code }}
    """,
    "verify.html": """
        <form method="post">
            <input type="text" name="user_id" required>
            <input type="text" name="code" required>
            <button type="submit">Verify</button>
        </form>
    """,
    "success.html": """
        Email verified successfully!
    """,
    "error.html": """
        Verification failed!
    """,
    "login.html": """
        <form method="post">
            <input type="text" name="user_id" required>
            <button type="submit">Login</button>
        </form>
    """,
    "unverified_users.html": """
        <ul>
            {% for user in users %}
                <li>{{ user.username }} ({{ user.email }})</li>
            {% endfor %}
        </ul>
    """,
    "admin_force_verify.html": """
        <form method="post">
            <button type="submit">Force Verify</button>
        </form>
    """
}

@app.get("/register")
async def register_form(request: Request):
    return render_template_string(html_templates["register.html"], request=request)

@app.post("/register")
async def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect("mock_db.sqlite3")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email,))
    if c.fetchone():
        return render_template_string("<p>Email already exists.</p>")
    verification_code = secrets.token_hex(3).upper()
    verification_expires = datetime.now() + timedelta(minutes=10)
    c.execute("INSERT INTO users (username, email, password, email_verified, verification_code, verification_expires) VALUES (?, ?, ?, ?, ?, ?)", (username, email, password, 0, verification_code, verification_expires))
    conn.commit()
    conn.close()
    return render_template_string(html_templates["send_verification.html"], request=request, verification_code=verification_code)

@app.get("/auth/send/{user_id}")
async def send_verification(request: Request, user_id: int):
    conn = sqlite3.connect("mock_db.sqlite3")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user or user[4]:
        return render_template_string("<p>User not found or already verified.</p>")
    verification_code = secrets.token_hex(3).upper()
    verification_expires = datetime.now() + timedelta(minutes=10)
    c.execute("UPDATE users SET verification_code = ?, verification_expires = ? WHERE user_id = ?", (verification_code, verification_expires, user_id))
    conn.commit()
    conn.close()
    return render_template_string(html_templates["send_verification.html"], request=request, verification_code=verification_code)

@app.get("/auth/verify")
async def verify_form(request: Request):
    return render_template_string(html_templates["verify.html"], request=request)

@app.post("/auth/verify")
async def verify(request: Request, user_id: str = Form(...), code: str = Form(...)):
    conn = sqlite3.connect("mock_db.sqlite3")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user or user[4] or user[5] != code or user[6] < datetime.now():
        return render_template_string(html_templates["error.html"], request=request)
    c.execute("UPDATE users SET email_verified = 1, verification_code = NULL, verification_expires = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return render_template_string(html_templates["success.html"], request=request)

@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    conn = sqlite3.connect("mock_db.sqlite3")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ? AND email_verified = 1", (user_id,))
    user = c.fetchone()
    if not user:
        return render_template_string("<p>User not found or not verified.</p>")
    request.session["user_id"] = user_id
    request.session["is_admin"] = user[3]
    return render_template_string("<p>Logged in successfully.</p>", request=request)

@app.get("/admin/unverified")
async def admin_unverified(request: Request):
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return render_template_string("<p>Admin only.</p>", request=request)
    conn = sqlite3.connect("mock_db.sqlite3")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email_verified = 0")
    users = c.fetchall()
    conn.close()
    return render_template_string(html_templates["unverified_users.html"], request=request, users=users)

@app.post("/admin/force_verify/{user_id}")
async def admin_force_verify(request: Request, user_id: int):
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        return render_template_string("<p>Admin only.</p>", request=request)
    conn = sqlite3.connect("mock_db.sqlite3")
    c = conn.cursor()
    c.execute("UPDATE users SET email_verified = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return render_template_string("<p>User verified successfully.</p>", request=request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)