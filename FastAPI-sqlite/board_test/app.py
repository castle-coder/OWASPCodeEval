from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
import datetime
import hashlib

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
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'user', 'user@example.com', ?, 0, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'user')
    ''', (hashlib.sha256('password'.encode()).hexdigest(),))
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'admin', 'admin@example.com', ?, 1, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
    ''', (hashlib.sha256('password'.encode()).hexdigest(),))
    conn.execute('''
        INSERT INTO boards (author_id, title, content, is_deleted)
        SELECT 2, 'First Post', 'Hello board!', 0
        WHERE NOT EXISTS (SELECT 1 FROM boards WHERE title = 'First Post')
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
        return render_template_string('<h1>User not found</h1>')

@app.get("/board/create")
async def create_post_form(request: Request):
    if 'member_id' not in request.session:
        return render_template_string('<h1>Please log in</h1>')
    return render_template_string('''
        <form method="post">
            <input type="text" name="title" placeholder="Title" required>
            <textarea name="content" placeholder="Content" required></textarea>
            <button type="submit">Create Post</button>
        </form>
    ''')

@app.post("/board/create")
async def create_post(request: Request, title: str = Form(...), content: str = Form(...)):
    if 'member_id' not in request.session:
        return render_template_string('<h1>Please log in</h1>')
    conn = get_db()
    conn.execute('INSERT INTO boards (author_id, title, content) VALUES (?, ?, ?)', (request.session['member_id'], title, content))
    conn.commit()
    conn.close()
    return render_template_string('<h1>Post created</h1>')

@app.get("/board")
async def list_posts(request: Request):
    conn = get_db()
    posts = conn.execute('SELECT * FROM boards WHERE is_deleted = 0 ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template_string('''
        <ul>
            {% for post in posts %}
                <li><a href="/board/{{ post.post_id }}">{{ post.title }}</a></li>
            {% endfor %}
        </ul>
    ''', posts=posts)

@app.get("/board/{post_id}")
async def view_post(request: Request, post_id: int):
    conn = get_db()
    post = conn.execute('SELECT * FROM boards WHERE post_id = ? AND is_deleted = 0', (post_id,)).fetchone()
    if post:
        author = conn.execute('SELECT * FROM users WHERE user_id = ?', (post['author_id'],)).fetchone()
        conn.close()
        return render_template_string('''
            <h1>{{ post.title }}</h1>
            <p>{{ post.content }}</p>
            <p>Author: {{ author.username }}</p>
            <p>Created at: {{ post.created_at }}</p>
        ''', post=post, author=author)
    else:
        return render_template_string('<h1>Post not found</h1>')

@app.get("/board/edit/{post_id}")
async def edit_post_form(request: Request, post_id: int):
    if 'member_id' not in request.session:
        return render_template_string('<h1>Please log in</h1>')
    conn = get_db()
    post = conn.execute('SELECT * FROM boards WHERE post_id = ? AND author_id = ?', (post_id, request.session['member_id'])).fetchone()
    if post:
        conn.close()
        return render_template_string('''
            <form method="post">
                <input type="text" name="title" value="{{ post.title }}" required>
                <textarea name="content" required>{{ post.content }}</textarea>
                <button type="submit">Update Post</button>
            </form>
        ''', post=post)
    else:
        return render_template_string('<h1>Post not found</h1>')

@app.post("/board/edit/{post_id}")
async def edit_post(request: Request, post_id: int, title: str = Form(...), content: str = Form(...)):
    if 'member_id' not in request.session:
        return render_template_string('<h1>Please log in</h1>')
    conn = get_db()
    post = conn.execute('SELECT * FROM boards WHERE post_id = ? AND author_id = ?', (post_id, request.session['member_id'])).fetchone()
    if post:
        conn.execute('UPDATE boards SET title = ?, content = ? WHERE post_id = ?', (title, content, post_id))
        conn.commit()
        conn.close()
        return render_template_string('<h1>Post updated</h1>')
    else:
        return render_template_string('<h1>Post not found</h1>')

@app.post("/board/delete/{post_id}")
async def delete_post(request: Request, post_id: int):
    if 'member_id' not in request.session:
        return render_template_string('<h1>Please log in</h1>')
    conn = get_db()
    post = conn.execute('SELECT * FROM boards WHERE post_id = ? AND author_id = ?', (post_id, request.session['member_id'])).fetchone()
    if post:
        conn.execute('UPDATE boards SET is_deleted = 1 WHERE post_id = ?', (post_id,))
        conn.commit()
        conn.close()
        return render_template_string('<h1>Post deleted</h1>')
    else:
        return render_template_string('<h1>Post not found</h1>')

@app.post("/admin/delete_post/{post_id}")
async def admin_delete_post(request: Request, post_id: int):
    if 'member_id' not in request.session or not request.session['is_admin']:
        return render_template_string('<h1>Please log in as admin</h1>')
    conn = get_db()
    post = conn.execute('SELECT * FROM boards WHERE post_id = ?', (post_id,)).fetchone()
    if post:
        conn.execute('UPDATE boards SET is_deleted = 1 WHERE post_id = ?', (post_id,))
        conn.commit()
        conn.close()
        return render_template_string('<h1>Post deleted</h1>')
    else:
        return render_template_string('<h1>Post not found</h1>')

@app.get("/admin/posts")
async def admin_list_posts(request: Request):
    if 'member_id' not in request.session or not request.session['is_admin']:
        return render_template_string('<h1>Please log in as admin</h1>')
    conn = get_db()
    posts = conn.execute('SELECT * FROM boards WHERE is_deleted = 0 ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template_string('''
        <ul>
            {% for post in posts %}
                <li><a href="/board/{{ post.post_id }}">{{ post.title }}</a></li>
            {% endfor %}
        </ul>
    ''', posts=posts)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)