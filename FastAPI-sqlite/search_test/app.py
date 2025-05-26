from fastapi import FastAPI, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
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
async def login(request: Request, member_id: str):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (member_id,)).fetchone()
    if user:
        request.session['member_id'] = user['user_id']
        request.session['is_admin'] = user['is_admin']
        return render_template_string('<h1>Logged in as {{ member_id }}</h1>', member_id=member_id)
    else:
        raise HTTPException(status_code=404, detail="User not found")

@app.get("/search")
async def search(request: Request, q: str):
    if 'member_id' not in request.session:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    results = conn.execute('SELECT * FROM boards_fts WHERE title MATCH ? OR content MATCH ?', (q, q)).fetchall()
    html = '<ul>'
    for result in results:
        html += f'<li><a href="/post/{result["post_id"]}">{result["title"]}</a></li>'
    html += '</ul>'
    return render_template_string(html)

@app.post("/admin/reindex")
async def reindex(request: Request):
    if 'member_id' not in request.session or not request.session['is_admin']:
        raise HTTPException(status_code=401, detail="Not authorized")
    conn = get_db()
    conn.execute('DELETE FROM boards_fts')
    conn.execute('INSERT INTO boards_fts (title, content, post_id) SELECT title, content, post_id FROM boards')
    conn.commit()
    return render_template_string('<h1>Search index rebuilt</h1>')

@app.get("/post/{post_id}")
async def post(request: Request, post_id: int):
    if 'member_id' not in request.session:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    post = conn.execute('SELECT * FROM boards WHERE post_id = ?', (post_id,)).fetchone()
    if post and not post['is_deleted']:
        return render_template_string('<h1>{{ title }}</h1><p>{{ content }}</p>', title=post['title'], content=post['content'])
    else:
        return render_template_string('<h1>Post not found</h1>')

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)