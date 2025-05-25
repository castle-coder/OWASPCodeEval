from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime
import sqlite3

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
    if not request.session.get("user_id") or not request.session.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in or not admin")
    return templates.TemplateResponse("admin.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)