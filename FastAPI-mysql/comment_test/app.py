from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import sqlite3
from datetime import datetime

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DATABASE = "mock_db.sqlite3"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    request.session["user_id"] = user_id
    request.session["is_admin"] = user_id == 2
    return RedirectResponse("/")

@app.post("/comments")
async def create_comment(request: Request, post_id: int, title: str = Form(...), content: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO comments (post_id, user_id, title, content) VALUES (?, ?, ?, ?)", (post_id, user_id, title, content))
    conn.commit()
    return RedirectResponse("/")

@app.post("/comments/edit/{comment_id}")
async def edit_comment(request: Request, comment_id: int, title: str = Form(...), content: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM comments WHERE id = ?", (comment_id,))
    comment_user_id = cursor.fetchone()[0]
    if comment_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    cursor.execute("UPDATE comments SET title = ?, content = ?, updated_at = ? WHERE id = ?", (title, content, datetime.now(), comment_id))
    conn.commit()
    return RedirectResponse("/")

@app.post("/comments/delete/{comment_id}")
async def delete_comment(request: Request, comment_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM comments WHERE id = ?", (comment_id,))
    comment_user_id = cursor.fetchone()[0]
    if comment_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    cursor.execute("UPDATE comments SET is_deleted = 1 WHERE id = ?", (comment_id,))
    conn.commit()
    return RedirectResponse("/")

@app.get("/posts/{post_id}/comments")
async def view_comments(request: Request, post_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM comments WHERE post_id = ? AND is_deleted = 0", (post_id,))
    comments = cursor.fetchall()
    return templates.TemplateResponse("comments.html", {"request": request, "comments": comments})

@app.post("/admin/block/{comment_id}")
async def block_comment(request: Request, comment_id: int):
    user_id = request.session.get("user_id")
    if not user_id or not request.session.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in or not admin")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE comments SET is_blocked = 1 WHERE id = ?", (comment_id,))
    conn.commit()
    return RedirectResponse("/")

@app.post("/comments/report/{comment_id}")
async def report_comment(request: Request, comment_id: int, reason: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reports (comment_id, user_id, reason) VALUES (?, ?, ?)", (comment_id, user_id, reason))
    conn.commit()
    return RedirectResponse("/")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/admin")
async def admin(request: Request):
    user_id = request.session.get("user_id")
    if not user_id or not request.session.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in or not admin")
    return templates.TemplateResponse("admin.html", {"request": request})

if __name__ == "__main__":
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, is_admin BOOLEAN)")
    cursor.execute("CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER, user_id INTEGER, title TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_deleted BOOLEAN DEFAULT 0, is_blocked BOOLEAN DEFAULT 0, FOREIGN KEY (user_id) REFERENCES users(user_id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS reports (report_id INTEGER PRIMARY KEY AUTOINCREMENT, comment_id INTEGER, user_id INTEGER, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (comment_id) REFERENCES comments(id), FOREIGN KEY (user_id) REFERENCES users(user_id))")
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    cursor.execute("INSERT INTO comments (post_id, user_id, title, content) VALUES (?, ?, ?, ?)", (1, 1, 'First Comment', 'This is a comment.'))
    cursor.execute("INSERT INTO comments (post_id, user_id, title, content) VALUES (?, ?, ?, ?)", (1, 2, 'Admin Reply', 'Admin’s reply.'))
    cursor.execute("INSERT INTO reports (comment_id, user_id, reason) VALUES (?, ?, ?)", (1, 2, 'Inappropriate language'))
    conn.commit()
    conn.close()