from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse, RedirectResponse
from jinja2 import Template
import sqlite3
import hashlib

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="your_secret_key_here")

# Initialize the database
def init_db():
    conn = sqlite3.connect('mock_db.sqlite3')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0
        )
    ''')
    c.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)", ('user', 'user@example.com', hashlib.sha256('password'.encode()).hexdigest(), 0, 0))
    c.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)", ('admin', 'admin@example.com', hashlib.sha256('password'.encode()).hexdigest(), 1, 0))
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

@app.get("/")
async def index(request: Request):
    return render_template_string('''
        <h1>Welcome to the Community Website</h1>
        <a href="/register">Register</a>
        <a href="/login/1">Login as User</a>
        <a href="/login/2">Login as Admin</a>
    ''')

@app.get("/register")
async def register():
    return render_template_string('''
        <h1>Register</h1>
        <form method="post">
            <input type="text" name="username" placeholder="Username" required>
            <input type="email" name="email" placeholder="Email" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Register</button>
        </form>
    ''')

@app.post("/register")
async def register_post(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)", (username, email, hashlib.sha256(password.encode()).hexdigest(), 0, 0))
    conn.commit()
    conn.close()
    return RedirectResponse("/login/1", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    session = request.session
    session['member_id'] = member_id
    session['is_admin'] = member_id == 2
    return RedirectResponse("/profile", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/profile")
async def profile(request: Request):
    session = request.session
    member_id = session.get('member_id')
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (member_id,))
    user = c.fetchone()
    conn.close()
    return render_template_string('''
        <h1>Profile</h1>
        <form method="post" action="/profile/update">
            <input type="text" name="username" value="{{ user['username'] }}" required>
            <input type="email" name="email" value="{{ user['email'] }}" required>
            <input type="password" name="password" placeholder="New Password">
            <button type="submit">Update Profile</button>
        </form>
        <form method="post" action="/profile/delete">
            <button type="submit">Delete Account</button>
        </form>
    ''', user=user)

@app.post("/profile/update")
async def profile_update(username: str = Form(...), email: str = Form(...), password: str = Form(None)):
    session = request.session
    member_id = session.get('member_id')
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    c = conn.cursor()
    if password:
        new_password = hashlib.sha256(password.encode()).hexdigest()
    else:
        new_password = None
    c.execute("UPDATE users SET username = ?, email = ?, password = ? WHERE user_id = ?", (username, email, new_password, member_id) if new_password else (username, email, None, member_id))
    conn.commit()
    conn.close()
    return RedirectResponse("/profile", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/profile/delete")
async def profile_delete(request: Request):
    session = request.session
    member_id = session.get('member_id')
    if not member_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_deleted = 1 WHERE user_id = ?", (member_id,))
    session.clear()
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/delete_member/{member_id}")
async def admin_delete_member(request: Request, member_id: int):
    session = request.session
    if not session.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not an admin")
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_deleted = 1 WHERE user_id = ?", (member_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin/members", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/admin/members")
async def admin_members(request: Request):
    session = request.session
    if not session.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not an admin")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE is_deleted = 0 ORDER BY user_id DESC")
    members = c.fetchall()
    conn.close()
    return render_template_string('''
        <h1>Active Members</h1>
        <ul>
            {% for member in members %}
                <li>{{ member['username'] }} ({{ member['email'] }})</li>
            {% endfor %}
        </ul>
    ''', members=members)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)