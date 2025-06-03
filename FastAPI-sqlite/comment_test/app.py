from fastapi import FastAPI, Request, Form, Depends, HTTPException
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

@app.on_event("startup")
async def startup_event():
    db = get_db()
    cursor = db.cursor()
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
        CREATE TABLE IF NOT EXISTS comments (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)",
                   ('user', 'user@example.com', '<hashed>', 0, 0))
    cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)",
                   ('admin', 'admin@example.com', '<hashed>', 1, 0))
    cursor.execute("INSERT INTO comments (author_id, content, is_deleted) VALUES (?, ?, ?)", (2, 'Welcome to the site!', 0))
    db.commit()
    db.close()

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

@app.get("/login/{member_id}")
async def login(request: Request, member_id: str):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (member_id,))
    user = cursor.fetchone()
    if user:
        request.session["member_id"] = member_id
        request.session["is_admin"] = user['is_admin']
        return render_template_string("<html><body>Logged in as {{ user_id }}</body></html>", user_id=member_id)
    else:
        return render_template_string("<html><body>User not found</body></html>")

@app.get("/comments/create")
async def create_comment_form(request: Request):
    if "member_id" not in request.session:
        return render_template_string("<html><body>Please log in</body></html>")
    return render_template_string("<html><body><form method='post'>Content: <input type='text' name='content'><input type='submit' value='Add Comment'></form></body></html>")

@app.post("/comments/create")
async def create_comment(request: Request, content: str = Form(...)):
    if "member_id" not in request.session:
        return render_template_string("<html><body>Please log in</body></html>")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO comments (author_id, content) VALUES (?, ?)", (request.session["member_id"], content))
    db.commit()
    db.close()
    return render_template_string("<html><body>Comment added</body></html>")

@app.get("/comments")
async def list_my_comments(request: Request):
    if "member_id" not in request.session:
        return render_template_string("<html><body>Please log in</body></html>")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM comments WHERE author_id = ? AND is_deleted = 0 ORDER BY created_at DESC", (request.session["member_id"],))
    comments = cursor.fetchall()
    db.close()
    return render_template_string("<html><body><ul>{% for comment in comments %}<li>{{ comment.content }}</li>{% endfor %}</ul></body></html>", comments=comments)

@app.get("/comments/edit/{comment_id}")
async def edit_comment_form(request: Request, comment_id: int):
    if "member_id" not in request.session:
        return render_template_string("<html><body>Please log in</body></html>")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM comments WHERE comment_id = ? AND author_id = ? AND is_deleted = 0", (comment_id, request.session["member_id"]))
    comment = cursor.fetchone()
    if comment:
        return render_template_string("<html><body><form method='post'><input type='hidden' name='comment_id' value='{{ comment_id }}'><input type='text' name='content' value='{{ comment.content }}'><input type='submit' value='Update Comment'></form></body></html>", comment_id=comment_id, comment=comment)
    else:
        return render_template_string("<html><body>Comment not found</body></html>")

@app.post("/comments/edit/{comment_id}")
async def edit_comment(request: Request, comment_id: int, content: str = Form(...)):
    if "member_id" not in request.session:
        return render_template_string("<html><body>Please log in</body></html>")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM comments WHERE comment_id = ? AND author_id = ? AND is_deleted = 0", (comment_id, request.session["member_id"]))
    comment = cursor.fetchone()
    if comment:
        cursor.execute("UPDATE comments SET content = ? WHERE comment_id = ?", (content, comment_id))
        db.commit()
        db.close()
        return render_template_string("<html><body>Comment updated</body></html>")
    else:
        return render_template_string("<html><body>Comment not found</body></html>")

@app.post("/comments/delete/{comment_id}")
async def delete_comment(request: Request, comment_id: int):
    if "member_id" not in request.session:
        return render_template_string("<html><body>Please log in</body></html>")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM comments WHERE comment_id = ? AND author_id = ? AND is_deleted = 0", (comment_id, request.session["member_id"]))
    comment = cursor.fetchone()
    if comment:
        cursor.execute("UPDATE comments SET is_deleted = 1 WHERE comment_id = ?", (comment_id,))
        db.commit()
        db.close()
        return render_template_string("<html><body>Comment deleted</body></html>")
    else:
        return render_template_string("<html><body>Comment not found</body></html>")

@app.post("/admin/delete_comment/{comment_id}")
async def admin_delete_comment(request: Request, comment_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return render_template_string("<html><body>Please log in as admin</body></html>")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM comments WHERE comment_id = ? AND is_deleted = 0", (comment_id,))
    comment = cursor.fetchone()
    if comment:
        cursor.execute("UPDATE comments SET is_deleted = 1 WHERE comment_id = ?", (comment_id,))
        db.commit()
        db.close()
        return render_template_string("<html><body>Comment deleted</body></html>")
    else:
        return render_template_string("<html><body>Comment not found</body></html>")

@app.get("/admin/comments")
async def list_admin_comments(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return render_template_string("<html><body>Please log in as admin</body></html>")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM comments WHERE is_deleted = 0 ORDER BY created_at DESC")
    comments = cursor.fetchall()
    db.close()
    return render_template_string("<html><body><ul>{% for comment in comments %}<li>{{ comment.content }}</li>{% endfor %}</ul></body></html>", comments=comments)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)