from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
import datetime

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
        CREATE TABLE IF NOT EXISTS comments (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute("INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)", ('user', 'user@example.com', '<hashed>', 0))
    cursor.execute("INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)", ('admin', 'admin@example.com', '<hashed>', 1))
    cursor.execute("INSERT INTO comments (author_id, content, is_deleted) VALUES (?, ?, ?)", (2, 'Welcome to the site!', 0))
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    return render_template_string('<html><body><h1>Create Comment</h1><form method="post" action="/comments/create"><textarea name="content"></textarea><input type="submit" value="Submit"></form></body></html>')

@app.post("/comments/create")
async def create_comment(request: Request, content: str = Form(...)):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO comments (author_id, content) VALUES (?, ?)", (request.session["member_id"], content))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Comment created</h1><a href="/comments">Back to comments</a></body></html>')

@app.get("/comments")
async def list_comments(request: Request):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM comments WHERE author_id = ? AND is_deleted = 0 ORDER BY created_at DESC", (request.session["member_id"],))
    comments = cursor.fetchall()
    conn.close()
    return render_template_string('<html><body><h1>My Comments</h1><ul>{{ comments|join(\'<li>\') }}</li></ul><a href="/comments/create">Create Comment</a></body></html>', comments=[f"{comment['content']} - {comment['created_at']}" for comment in comments])

@app.get("/comments/edit/{comment_id}")
async def edit_comment_form(request: Request, comment_id: int):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM comments WHERE comment_id = ? AND author_id = ?", (comment_id, request.session["member_id"]))
    comment = cursor.fetchone()
    conn.close()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return render_template_string('<html><body><h1>Edit Comment</h1><form method="post" action="/comments/edit/{{ comment_id }}"><textarea name="content">{{ comment["content"] }}</textarea><input type="submit" value="Submit"></form></body></html>', comment_id=comment_id, comment=comment)

@app.post("/comments/edit/{comment_id}")
async def edit_comment(request: Request, comment_id: int, content: str = Form(...)):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM comments WHERE comment_id = ? AND author_id = ?", (comment_id, request.session["member_id"]))
    comment = cursor.fetchone()
    conn.close()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    cursor.execute("UPDATE comments SET content = ? WHERE comment_id = ?", (content, comment_id))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Comment edited</h1><a href="/comments">Back to comments</a></body></html>')

@app.post("/comments/delete/{comment_id}")
async def delete_comment(request: Request, comment_id: int):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM comments WHERE comment_id = ? AND author_id = ?", (comment_id, request.session["member_id"]))
    comment = cursor.fetchone()
    conn.close()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    cursor.execute("UPDATE comments SET is_deleted = 1 WHERE comment_id = ?", (comment_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Comment deleted</h1><a href="/comments">Back to comments</a></body></html>')

@app.post("/admin/delete_comment/{comment_id}")
async def admin_delete_comment(request: Request, comment_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE comments SET is_deleted = 1 WHERE comment_id = ?", (comment_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Comment deleted</h1><a href="/admin/comments">Back to admin comments</a></body></html>')

@app.get("/admin/comments")
async def admin_list_comments(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM comments WHERE is_deleted = 0 ORDER BY created_at DESC")
    comments = cursor.fetchall()
    conn.close()
    return render_template_string('<html><body><h1>Admin Comments</h1><ul>{{ comments|join(\'<li>\') }}</li></ul></body></html>', comments=[f"{comment['content']} - {comment['created_at']}" for comment in comments])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)