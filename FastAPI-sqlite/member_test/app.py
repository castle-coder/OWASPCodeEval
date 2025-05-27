from fastapi import FastAPI, Request, Form, HTTPException, Depends, Session
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
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
            is_deleted BOOLEAN DEFAULT 0
        )
    ''')
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'user', 'user@example.com', ?, 0, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'user')
    ''', (hashlib.sha256('password'.encode()).hexdigest(),))
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'admin', 'admin@example.com', ?, 1, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
    ''', (hashlib.sha256('adminpassword'.encode()).hexdigest(),))
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
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, hashed_password))
    conn.commit()
    conn.close()
    return render_template_string("<h1>Registration successful!</h1>")

@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    session = request.session
    session['member_id'] = member_id
    session['is_admin'] = False
    return render_template_string("<h1>Logged in!</h1>")

@app.get("/profile")
async def profile_form(request: Request, session: Session = Depends(get_db)):
    if 'member_id' not in session:
        return render_template_string("<h1>Please log in first.</h1>")
    member_id = session['member_id']
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (member_id,)).fetchone()
    if not user:
        return render_template_string("<h1>User not found.</h1>")
    html = f"""
        <form method="post" action="/profile/update">
            <input type="text" name="username" value="{user['username']}" required>
            <input type="email" name="email" value="{user['email']}" required>
            <input type="password" name="password" placeholder="New Password">
            <button type="submit">Update Profile</button>
        </form>
    """
    return render_template_string(html)

@app.post("/profile/update")
async def update_profile(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(None), session: Session = Depends(get_db)):
    if 'member_id' not in session:
        return render_template_string("<h1>Please log in first.</h1>")
    member_id = session['member_id']
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (member_id,)).fetchone()
    if not user:
        return render_template_string("<h1>User not found.</h1>")
    if password:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        conn.execute('UPDATE users SET username = ?, email = ?, password = ? WHERE user_id = ?', (username, email, hashed_password, member_id))
    else:
        conn.execute('UPDATE users SET username = ?, email = ? WHERE user_id = ?', (username, email, member_id))
    conn.commit()
    conn.close()
    return render_template_string("<h1>Profile updated successfully!</h1>")

@app.post("/profile/delete")
async def delete_profile(request: Request, session: Session = Depends(get_db)):
    if 'member_id' not in session:
        return render_template_string("<h1>Please log in first.</h1>")
    member_id = session['member_id']
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (member_id,)).fetchone()
    if not user:
        return render_template_string("<h1>User not found.</h1>")
    conn.execute('UPDATE users SET is_deleted = 1 WHERE user_id = ?', (member_id,))
    session.clear()
    conn.commit()
    conn.close()
    return render_template_string("<h1>Account deleted successfully!</h1>")

@app.post("/admin/delete_member/{member_id}")
async def admin_delete_member(request: Request, member_id: int, session: Session = Depends(get_db)):
    if 'member_id' not in session or not session['is_admin']:
        return render_template_string("<h1>Access denied.</h1>")
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (member_id,)).fetchone()
    if not user:
        return render_template_string("<h1>User not found.</h1>")
    conn.execute('UPDATE users SET is_deleted = 1 WHERE user_id = ?', (member_id,))
    conn.commit()
    conn.close()
    return render_template_string("<h1>Member deleted successfully!</h1>")

@app.get("/admin/members")
async def list_members(request: Request, session: Session = Depends(get_db)):
    if 'member_id' not in session or not session['is_admin']:
        return render_template_string("<h1>Access denied.</h1>")
    conn = get_db()
    members = conn.execute('SELECT * FROM users WHERE is_deleted = 0 ORDER BY user_id DESC').fetchall()
    html = "<ul>"
    for member in members:
        html += f"<li>{member['username']} ({member['email']})</li>"
    html += "</ul>"
    return render_template_string(html)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)