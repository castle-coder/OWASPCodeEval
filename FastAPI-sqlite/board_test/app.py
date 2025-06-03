from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
from datetime import datetime

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key_here")

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
def startup():
    conn = get_db_connection()
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
        SELECT 2, 'First Post', 'Hello board!', 0
        WHERE NOT EXISTS (SELECT 1 FROM boards WHERE title = 'First Post')
    ''')
    conn.commit()
    conn.close()

@app.get("/login/{member_id}")
async def login(request: Request, member_id: str):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND is_deleted = 0', (member_id,)).fetchone()
    if user:
        request.session['member_id'] = user['user_id']
        request.session['is_admin'] = user['is_admin']
    return render_template_string('<html><body><h1>Logged in as {{ member_id }}</h1></body></html>', member_id=member_id)

@app.get("/board/create")
async def create_post(request: Request):
    if 'member_id' not in request.session:
        return render_template_string('<html><body><h1>Please log in to create a post.</h1></body></html>')
    return render_template_string('''
        <html>
        <body>
            <h1>Create Post</h1>
            <form method="post">
                <label for="title">Title:</label>
                <input type="text" id="title" name="title" required><br><br>
                <label for="content">Content:</label>
                <textarea id="content" name="content" required></textarea><br><br>
                <input type="submit" value="Create">
            </form>
        </body>
        </html>
    ''')

@app.post("/board/create")
async def create_post_process(request: Request, title: str = Form(...), content: str = Form(...)):
    if 'member_id' not in request.session:
        return render_template_string('<html><body><h1>Please log in to create a post.</h1></body></html>')
    conn = get_db_connection()
    conn.execute('INSERT INTO boards (author_id, title, content, is_deleted) VALUES (?, ?, ?, 0)', (request.session['member_id'], title, content))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Post created successfully.</h1></body></html>')

@app.get("/board")
async def list_posts(request: Request):
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM boards WHERE is_deleted = 0 ORDER BY created_at DESC').fetchall()
    conn.close()
    post_list = '<ul>'
    for post in posts:
        post_list += f'<li><a href="/board/{post["post_id"]}">{post["title"]}</a></li>'
    post_list += '</ul>'
    return render_template_string(f'''
        <html>
        <body>
            <h1>Board</h1>
            {post_list}
        </body>
        </html>
    ''')

@app.get("/board/{post_id}")
async def view_post(request: Request, post_id: int):
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM boards WHERE post_id = ? AND is_deleted = 0', (post_id,)).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (post['author_id'],)).fetchone()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>{{ post.title }}</h1>
            <p>{{ post.content }}</p>
            <p>Author: {{ user.username }}</p>
            <p>Created at: {{ post.created_at }}</p>
        </body>
        </html>
    ''', post=post, user=user)

@app.get("/board/edit/{post_id}")
async def edit_post(request: Request, post_id: int):
    if 'member_id' not in request.session:
        return render_template_string('<html><body><h1>Please log in to edit a post.</h1></body></html>')
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM boards WHERE post_id = ? AND is_deleted = 0', (post_id,)).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post['author_id'] != request.session['member_id']:
        return render_template_string('<html><body><h1>You do not have permission to edit this post.</h1></body></html>')
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>Edit Post</h1>
            <form method="post">
                <label for="title">Title:</label>
                <input type="text" id="title" name="title" value="{{ post.title }}" required><br><br>
                <label for="content">Content:</label>
                <textarea id="content" name="content" required>{{ post.content }}</textarea><br><br>
                <input type="submit" value="Update">
            </form>
        </body>
        </html>
    ''', post=post)

@app.post("/board/edit/{post_id}")
async def edit_post_process(request: Request, post_id: int, title: str = Form(...), content: str = Form(...)):
    if 'member_id' not in request.session:
        return render_template_string('<html><body><h1>Please log in to edit a post.</h1></body></html>')
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM boards WHERE post_id = ? AND is_deleted = 0', (post_id,)).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post['author_id'] != request.session['member_id']:
        return render_template_string('<html><body><h1>You do not have permission to edit this post.</h1></body></html>')
    conn.execute('UPDATE boards SET title = ?, content = ? WHERE post_id = ?', (title, content, post_id))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Post updated successfully.</h1></body></html>')

@app.post("/board/delete/{post_id}")
async def delete_post(request: Request, post_id: int):
    if 'member_id' not in request.session:
        return render_template_string('<html><body><h1>Please log in to delete a post.</h1></body></html>')
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM boards WHERE post_id = ?', (post_id,)).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post['author_id'] == request.session['member_id']:
        conn.execute('UPDATE boards SET is_deleted = 1 WHERE post_id = ?', (post_id,))
        conn.commit()
    else:
        return render_template_string('<html><body><h1>You do not have permission to delete this post.</h1></body></html>')
    conn.close()
    return render_template_string('<html><body><h1>Post deleted successfully.</h1></body></html>')

@app.post("/admin/delete_post/{post_id}")
async def admin_delete_post(request: Request, post_id: int):
    if 'member_id' not in request.session or not request.session['is_admin']:
        return render_template_string('<html><body><h1>Please log in as an admin to delete a post.</h1></body></html>')
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM boards WHERE post_id = ?', (post_id,)).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    conn.execute('UPDATE boards SET is_deleted = 1 WHERE post_id = ?', (post_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Post deleted successfully.</h1></body></html>')

@app.get("/admin/posts")
async def admin_list_posts(request: Request):
    if 'member_id' not in request.session or not request.session['is_admin']:
        return render_template_string('<html><body><h1>Please log in as an admin to view all posts.</h1></body></html>')
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM boards WHERE is_deleted = 0 ORDER BY created_at DESC').fetchall()
    conn.close()
    post_list = '<ul>'
    for post in posts:
        post_list += f'<li><a href="/board/{post["post_id"]}">{post["title"]}</a></li>'
    post_list += '</ul>'
    return render_template_string(f'''
        <html>
        <body>
            <h1>Admin Posts</h1>
            {post_list}
        </body>
        </html>
    ''')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)