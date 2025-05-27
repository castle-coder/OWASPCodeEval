from fastapi import FastAPI, Request, Form, HTTPException, Depends
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse
from jinja2 import Template
import sqlite3
import uvicorn
from datetime import datetime

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
        CREATE TABLE IF NOT EXISTS comments (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL,
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
        INSERT INTO comments (author_id, content, is_deleted)
        SELECT 2, 'Welcome to the site!', 0
        WHERE NOT EXISTS (SELECT 1 FROM comments WHERE content = 'Welcome to the site!')
    ''')
    conn.commit()
    conn.close()

@app.get("/login/{member_id}")
async def login(request: Request, member_id: str):
    request.session["member_id"] = member_id
    request.session["is_admin"] = member_id == "admin"
    return render_template_string('<html><body><h1>Logged in as {{ member_id }}</h1></body></html>', member_id=member_id)

@app.get("/comments/create")
async def create_comment_form(request: Request):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in to create a comment.</h1></body></html>')
    return render_template_string('<html><body><form method="post"><textarea name="content"></textarea><button type="submit">Submit</button></form></body></html>')

@app.post("/comments/create")
async def create_comment(request: Request, content: str = Form(...)):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in to create a comment.</h1></body></html>')
    conn = get_db()
    conn.execute('INSERT INTO comments (author_id, content) VALUES (?, ?)', (request.session["member_id"], content))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Comment created.</h1></body></html>')

@app.get("/comments")
async def list_my_comments(request: Request):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in to view your comments.</h1></body></html>')
    conn = get_db()
    comments = conn.execute('SELECT * FROM comments WHERE author_id = ? AND is_deleted = 0 ORDER BY created_at DESC', (request.session["member_id"],)).fetchall()
    conn.close()
    return render_template_string('<html><body><h1>My Comments</h1><ul>{% for comment in comments %}<li>{{ comment.content }}</li>{% endfor %}</ul></body></html>', comments=comments)

@app.get("/comments/edit/{comment_id}")
async def edit_comment_form(request: Request, comment_id: int):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in to edit a comment.</h1></body></html>')
    conn = get_db()
    comment = conn.execute('SELECT * FROM comments WHERE comment_id = ? AND author_id = ? AND is_deleted = 0', (comment_id, request.session["member_id"])).fetchone()
    conn.close()
    if not comment:
        return render_template_string('<html><body><h1>Comment not found or not yours.</h1></body></html>')
    return render_template_string('<html><body><form method="post"><textarea name="content">{{ comment.content }}</textarea><button type="submit">Submit</button></form></body></html>', comment=comment)

@app.post("/comments/edit/{comment_id}")
async def edit_comment(request: Request, comment_id: int, content: str = Form(...)):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in to edit a comment.</h1></body></html>')
    conn = get_db()
    comment = conn.execute('SELECT * FROM comments WHERE comment_id = ? AND author_id = ? AND is_deleted = 0', (comment_id, request.session["member_id"])).fetchone()
    if not comment:
        return render_template_string('<html><body><h1>Comment not found or not yours.</h1></body></html>')
    conn.execute('UPDATE comments SET content = ? WHERE comment_id = ?', (content, comment_id))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Comment edited.</h1></body></html>')

@app.post("/comments/delete/{comment_id}")
async def delete_comment(request: Request, comment_id: int):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in to delete a comment.</h1></body></html>')
    conn = get_db()
    comment = conn.execute('SELECT * FROM comments WHERE comment_id = ? AND author_id = ? AND is_deleted = 0', (comment_id, request.session["member_id"])).fetchone()
    if not comment:
        return render_template_string('<html><body><h1>Comment not found or not yours.</h1></body></html>')
    conn.execute('UPDATE comments SET is_deleted = 1 WHERE comment_id = ?', (comment_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Comment deleted.</h1></body></html>')

@app.post("/admin/delete_comment/{comment_id}")
async def admin_delete_comment(request: Request, comment_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return render_template_string('<html><body><h1>Please log in as an admin to delete a comment.</h1></body></html>')
    conn = get_db()
    comment = conn.execute('SELECT * FROM comments WHERE comment_id = ?', (comment_id,)).fetchone()
    if not comment:
        return render_template_string('<html><body><h1>Comment not found.</h1></body></html>')
    conn.execute('UPDATE comments SET is_deleted = 1 WHERE comment_id = ?', (comment_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Comment deleted.</h1></body></html>')

@app.get("/admin/comments")
async def list_all_comments(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return render_template_string('<html><body><h1>Please log in as an admin to view all comments.</h1></body></html>')
    conn = get_db()
    comments = conn.execute('SELECT * FROM comments WHERE is_deleted = 0 ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template_string('<html><body><h1>All Comments</h1><ul>{% for comment in comments %}<li>{{ comment.content }}</li>{% endfor %}</ul></body></html>', comments=comments)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)