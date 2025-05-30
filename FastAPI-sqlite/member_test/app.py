from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
import hashlib
import uvicorn

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key_here")

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

def get_db():
    conn = sqlite3.connect("mock_db.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn

def get_session(request: Request):
    return request.session

@app.on_event("startup")
async def startup_event():
    conn = sqlite3.connect("mock_db.sqlite3")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0
        )
    ''')
    cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)", ('user', 'user@example.com', hashlib.sha256('password'.encode()).hexdigest(), 0, 0))
    cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)", ('admin', 'admin@example.com', hashlib.sha256('adminpassword'.encode()).hexdigest(), 1, 0))
    conn.commit()
    conn.close()

@app.get("/register")
async def register_form(request: Request):
    return render_template_string('''
        <form method="post" action="/register">
            <input type="text" name="username" placeholder="Username" required>
            <input type="email" name="email" placeholder="Email" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Register</button>
        </form>
    ''')

@app.post("/register")
async def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)", (username, email, hashlib.sha256(password.encode()).hexdigest(), 0, 0))
    conn.commit()
    conn.close()
    return render_template_string('''
        <p>Registration successful!</p>
        <a href="/">Back to home</a>
    ''')

@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    session = get_session(request)
    session["member_id"] = member_id
    session["is_admin"] = False
    return render_template_string('''
        <p>Logged in as member {member_id}</p>
        <a href="/">Back to home</a>
    ''')

@app.get("/profile")
async def profile_form(request: Request):
    session = get_session(request)
    if "member_id" not in session:
        raise HTTPException(status_code=403, detail="Not logged in")
    return render_template_string('''
        <form method="post" action="/profile/update">
            <input type="text" name="username" placeholder="Username" required>
            <input type="email" name="email" placeholder="Email" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Update Profile</button>
        </form>
    ''')

@app.post("/profile/update")
async def update_profile(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    session = get_session(request)
    if "member_id" not in session:
        raise HTTPException(status_code=403, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET username = ?, email = ?, password = ? WHERE user_id = ?", (username, email, hashlib.sha256(password.encode()).hexdigest(), session["member_id"]))
    conn.commit()
    conn.close()
    return render_template_string('''
        <p>Profile updated successfully!</p>
        <a href="/">Back to home</a>
    ''')

@app.post("/profile/delete")
async def delete_profile(request: Request):
    session = get_session(request)
    if "member_id" not in session:
        raise HTTPException(status_code=403, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_deleted = 1 WHERE user_id = ?", (session["member_id"],))
    conn.commit()
    conn.close()
    session.clear()
    return render_template_string('''
        <p>Account deleted successfully!</p>
        <a href="/">Back to home</a>
    ''')

@app.post("/admin/delete_member/{member_id}")
async def admin_delete_member(request: Request, member_id: int):
    session = get_session(request)
    if "member_id" not in session or not session["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_deleted = 1 WHERE user_id = ?", (member_id,))
    conn.commit()
    conn.close()
    return render_template_string('''
        <p>Member deleted successfully!</p>
        <a href="/">Back to home</a>
    ''')

@app.get("/admin/members")
async def list_members(request: Request):
    session = get_session(request)
    if "member_id" not in session or not session["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE is_deleted = 0 ORDER BY user_id DESC")
    members = cursor.fetchall()
    conn.close()
    return render_template_string('''
        <ul>
            {% for member in members %}
                <li>{{ member.username }} ({{ member.email }})</li>
            {% endfor %}
        </ul>
        <a href="/">Back to home</a>
    ''', members=members)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)