from fastapi import FastAPI, Request, HTTPException, Depends
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse
from jinja2 import Template
import sqlite3
import uvicorn
from datetime import datetime

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
        CREATE TABLE IF NOT EXISTS boards (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS boards_fts USING fts5(title, content, post_id UNINDEXED)
    ''')
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'user', 'user@example.com', '<hashed>', 0, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'user')
    ''')
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'admin', 'admin@example.com', '<hashed>', 1, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
    ''')
    conn.execute('''
        INSERT INTO boards (author_id, title, content, is_deleted)
        SELECT 2, 'Welcome', 'Hello community!', 0
        WHERE NOT EXISTS (SELECT 1 FROM boards WHERE title = 'Welcome')
    ''')
    conn.execute('''
        INSERT INTO boards (author_id, title, content, is_deleted)
        SELECT 2, 'FastAPI Tips', 'Use FastAPI for speedy APIs', 0
        WHERE NOT EXISTS (SELECT 1 FROM boards WHERE title = 'FastAPI Tips')
    ''')
    conn.execute('''
        INSERT INTO boards_fts (title, content, post_id)
        SELECT title, content, post_id FROM boards
    ''')
    conn.commit()
    conn.close()

@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    request.session["member_id"] = member_id
    request.session["is_admin"] = member_id == 1
    return render_template_string('<html><body>Logged in as {{ member_id }}</body></html>', member_id=member_id)

@app.get("/search")
async def search(request: Request, q: str):
    if "member_id" not in request.session:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.execute('''
        SELECT * FROM boards_fts WHERE title MATCH ? OR content MATCH ? AND is_deleted = 0
    ''', (q, q))
    posts = cursor.fetchall()
    conn.close()
    html = '<html><body><ul>'
    for post in posts:
        html += f'<li><a href="/post/{post["post_id"]}">{post["title"]}</a></li>'
    html += '</ul></body></html>'
    return render_template_string(html)

@app.post("/admin/reindex")
async def reindex(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    conn = get_db()
    conn.execute('DELETE FROM boards_fts')
    cursor = conn.execute('SELECT title, content, post_id FROM boards')
    rows = cursor.fetchall()
    for row in rows:
        conn.execute('INSERT INTO boards_fts (title, content, post_id) VALUES (?, ?, ?)', row)
    conn.commit()
    conn.close()
    return render_template_string('<html><body>Reindex completed</body></html>')

@app.get("/post/{post_id}")
async def post(request: Request, post_id: int):
    return render_template_string('<html><body>Coming soon</body></html>')

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)