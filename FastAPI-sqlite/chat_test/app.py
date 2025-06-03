from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
from datetime import datetime

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key="your_secret_key",
)

# Initialize database and insert dummy data
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES ('user', 'user@example.com', ?, 0, 0)", ('<hashed>',))
    c.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES ('admin', 'admin@example.com', ?, 1, 0)", ('<hashed>',))
    c.execute("INSERT INTO comments (author_id, content, is_deleted) VALUES (2, 'Welcome to the site!', 0)")
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect('mock_db.sqlite3')
    return conn

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

@app.get("/login/{member_id}")
async def login(request: Request, member_id: str):
    request.session["member_id"] = member_id
    request.session["is_admin"] = False
    return RedirectResponse("/")

@app.get("/comments/create")
async def create_comment_form(request: Request):
    member_id = request.session.get("member_id")
    if not member_id:
        return RedirectResponse("/login/user")
    return render_template_string("<h1>Create Comment</h1><form method='post'><textarea name='content' required></textarea><button type='submit'>Submit</button></form>")

@app.post("/comments/create")
async def create_comment(request: Request, content: str = Form(...)):
    member_id = request.session.get("member_id")
    if not member_id:
        return RedirectResponse("/login/user")
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO comments (author_id, content, is_deleted) VALUES (?, ?, 0)", (member_id, content))
    conn.commit()
    conn.close()
    return RedirectResponse("/comments")

@app.get("/comments")
async def list_comments(request: Request):
    member_id = request.session.get("member_id")
    if not member_id:
        return RedirectResponse("/login/user")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM comments WHERE author_id = ? AND is_deleted = 0 ORDER BY created_at DESC", (member_id,))
    comments = c.fetchall()
    conn.close()
    return render_template_string("<h1>My Comments</h1><ul>{% for comment in comments %}<li>{{ comment[2] }}</li>{% endfor %}</ul>", comments=comments)

@app.get("/comments/edit/{comment_id}")
async def edit_comment_form(request: Request, comment_id: int):
    member_id = request.session.get("member_id")
    if not member_id:
        return RedirectResponse("/login/user")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM comments WHERE comment_id = ? AND author_id = ? AND is_deleted = 0", (comment_id, member_id))
    comment = c.fetchone()
    conn.close()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found or not editable")
    return render_template_string("<h1>Edit Comment</h1><form method='post'><textarea name='content' required>{{ comment[2] }}</textarea><button type='submit'>Submit</button></form>", comment=comment)

@app.post("/comments/edit/{comment_id}")
async def edit_comment(request: Request, comment_id: int, content: str = Form(...)):
    member_id = request.session.get("member_id")
    if not member_id:
        return RedirectResponse("/login/user")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM comments WHERE comment_id = ? AND author_id = ? AND is_deleted = 0", (comment_id, member_id))
    comment = c.fetchone()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found or not editable")
    c.execute("UPDATE comments SET content = ? WHERE comment_id = ?", (content, comment_id))
    conn.commit()
    conn.close()
    return RedirectResponse("/comments")

@app.post("/comments/delete/{comment_id}")
async def delete_comment(request: Request, comment_id: int):
    member_id = request.session.get("member_id")
    if not member_id:
        return RedirectResponse("/login/user")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM comments WHERE comment_id = ? AND author_id = ? AND is_deleted = 0", (comment_id, member_id))
    comment = c.fetchone()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found or not editable")
    c.execute("UPDATE comments SET is_deleted = 1 WHERE comment_id = ?", (comment_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/comments")

@app.post("/admin/delete_comment/{comment_id}")
async def admin_delete_comment(request: Request, comment_id: int):
    if not request.session.get("member_id") or not request.session.get("is_admin"):
        return RedirectResponse("/")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM comments WHERE comment_id = ?", (comment_id,))
    comment = c.fetchone()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    c.execute("UPDATE comments SET is_deleted = 1 WHERE comment_id = ?", (comment_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin/comments")

@app.get("/admin/comments")
async def admin_list_comments(request: Request):
    if not request.session.get("member_id") or not request.session.get("is_admin"):
        return RedirectResponse("/")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM comments WHERE is_deleted = 0 ORDER BY created_at DESC")
    comments = c.fetchall()
    conn.close()
    return render_template_string("<h1>All Active Comments</h1><ul>{% for comment in comments %}<li>{{ comment[2] }}</li>{% endfor %}</ul>", comments=comments)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)