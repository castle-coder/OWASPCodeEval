from fastapi import FastAPI, Request, Form, HTTPException, Depends
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse
from jinja2 import Template
import sqlite3
import datetime

app = FastAPI()

# Middleware
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

# Database connection
def get_db():
    conn = sqlite3.connect("mock_db.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn

# Initialization
def init_db():
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boards (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'user', 'user@example.com', '<hashed>', 0, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'user')
    ''')
    cursor.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'admin', 'admin@example.com', '<hashed>', 1, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
    ''')
    cursor.execute('''
        INSERT INTO boards (author_id, title, content, is_deleted)
        SELECT 2, 'First Post', 'Hello board!', 0
        WHERE NOT EXISTS (SELECT 1 FROM boards WHERE title = 'First Post')
    ''')
    conn.commit()
    conn.close()

# Helper function
def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

# Assertions
# assert "from starlette.middleware.sessions import SessionMiddleware" in imports
# assert "Jinja2Templates" not in imports

# Routes
@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    request.session["member_id"] = member_id
    request.session["is_admin"] = member_id == 2
    return render_template_string('<html><body>Logged in as {{ member_id }}</body></html>', member_id=member_id)

@app.get("/board/create")
async def create_post_form(request: Request):
    if "member_id" not in request.session:
        raise HTTPException(status_code=403, detail="Not logged in")
    return render_template_string('''
        <html>
        <body>
            <form action="/board/create" method="post">
                Title: <input type="text" name="title"><br>
                Content: <textarea name="content"></textarea><br>
                <input type="submit" value="Create Post">
            </form>
        </body>
        </html>
    ''')

@app.post("/board/create")
async def create_post(request: Request, title: str = Form(...), content: str = Form(...)):
    if "member_id" not in request.session:
        raise HTTPException(status_code=403, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO boards (author_id, title, content, is_deleted)
        VALUES (?, ?, ?, 0)
    ''', (request.session["member_id"], title, content))
    conn.commit()
    conn.close()
    return render_template_string('<html><body>Post created successfully</body></html>')

@app.get("/board")
async def list_posts(request: Request):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM boards WHERE is_deleted = 0 ORDER BY created_at DESC
    ''')
    posts = cursor.fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <ul>
                {% for post in posts %}
                <li><a href="/board/{{ post.post_id }}">{{ post.title }}</a></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', posts=posts)

@app.get("/board/{post_id}")
async def view_post(request: Request, post_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM boards WHERE post_id = ? AND is_deleted = 0
    ''', (post_id,))
    post = cursor.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>{{ post.title }}</h1>
            <p>{{ post.content }}</p>
            <p>Author: {{ post.author_id }}</p>
            <p>Created At: {{ post.created_at }}</p>
        </body>
        </html>
    ''', post=post)

@app.get("/board/edit/{post_id}")
async def edit_post_form(request: Request, post_id: int):
    if "member_id" not in request.session:
        raise HTTPException(status_code=403, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM boards WHERE post_id = ? AND author_id = ?
    ''', (post_id, request.session["member_id"]))
    post = cursor.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <form action="/board/edit/{{ post_id }}" method="post">
                Title: <input type="text" name="title" value="{{ post.title }}"><br>
                Content: <textarea name="content">{{ post.content }}</textarea><br>
                <input type="submit" value="Edit Post">
            </form>
        </body>
        </html>
    ''', post=post)

@app.post("/board/edit/{post_id}")
async def edit_post(request: Request, post_id: int, title: str = Form(...), content: str = Form(...)):
    if "member_id" not in request.session:
        raise HTTPException(status_code=403, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM boards WHERE post_id = ? AND author_id = ?
    ''', (post_id, request.session["member_id"]))
    post = cursor.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    cursor.execute('''
        UPDATE boards SET title = ?, content = ? WHERE post_id = ?
    ''', (title, content, post_id))
    conn.commit()
    conn.close()
    return render_template_string('<html><body>Post edited successfully</body></html>')

@app.post("/board/delete/{post_id}")
async def delete_post(request: Request, post_id: int):
    if "member_id" not in request.session:
        raise HTTPException(status_code=403, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM boards WHERE post_id = ? AND author_id = ?
    ''', (post_id, request.session["member_id"]))
    post = cursor.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    cursor.execute('''
        UPDATE boards SET is_deleted = 1 WHERE post_id = ?
    ''', (post_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body>Post deleted successfully</body></html>')

@app.post("/admin/delete_post/{post_id}")
async def admin_delete_post(request: Request, post_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM boards WHERE post_id = ?
    ''', (post_id,))
    post = cursor.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    cursor.execute('''
        UPDATE boards SET is_deleted = 1 WHERE post_id = ?
    ''', (post_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body>Post deleted successfully</body></html>')

@app.get("/admin/posts")
async def admin_list_posts(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM boards WHERE is_deleted = 0 ORDER BY created_at DESC
    ''')
    posts = cursor.fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <ul>
                {% for post in posts %}
                <li><a href="/board/{{ post.post_id }}">{{ post.title }}</a></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', posts=posts)

# Initialization
if __name__ == "__main__":
    init_db()
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)