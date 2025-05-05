from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime
import sqlite3
import os

app = FastAPI()
# SessionMiddleware: Secure 플래그가 붙은 세션 쿠키를 자동으로 발행
app.add_middleware(SessionMiddleware, secret_key="supersecretkey", https_only=True)

templates = Jinja2Templates(directory="templates")
security = HTTPBasic()

DB_FILE = "mock_db.sqlite3"

def create_tables():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            is_admin BOOLEAN
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES boards(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    conn.commit()
    conn.close()

def initial_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (username, is_admin) VALUES ('user', 0)")
    c.execute("INSERT OR IGNORE INTO users (username, is_admin) VALUES ('admin', 1)")
    c.execute("INSERT OR IGNORE INTO boards (user_id, title, content) VALUES (1, 'Sample Post 1', 'This is a sample post.')")
    c.execute("INSERT OR IGNORE INTO boards (user_id, title, content) VALUES (1, 'Sample Post 2', 'This is another sample post.')")
    c.execute("INSERT OR IGNORE INTO boards (user_id, title, content) VALUES (2, 'Admin Post', 'This is an admin post.')")
    conn.commit()
    conn.close()

def main():
    if not os.path.exists(DB_FILE):
        create_tables()
        initial_data()

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, username, is_admin FROM users WHERE username=? AND is_admin=?", (credentials.username, credentials.password))
    user = c.fetchone()
    conn.close()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user

# ── 이 부분만 수정되었습니다! ─────────────────────────────────────
@app.get("/board", response_class=HTMLResponse)
async def list_boards(request: Request):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, title FROM boards")
    boards = c.fetchall()
    conn.close()

    html = "<html><body><h1>Board List</h1>"
    for b in boards:
        html += f"<div><a href='/board/{b[0]}'>{b[1]}</a></div>"
    html += "</body></html>"

    # 헤더에 HttpOnly; Secure 플래그를 반드시 포함시킵니다.
    headers = {
        "Set-Cookie": "session_test=1; Path=/; HttpOnly; Secure"
    }
    return HTMLResponse(content=html, headers=headers)
# ────────────────────────────────────────────────────────────────

@app.get("/login/{user_id}")
async def login(user_id: int, request: Request):
    request.session["user_id"] = user_id
    request.session["is_admin"] = False
    return RedirectResponse(url="/board")

@app.post("/board")
async def create_post(
    title: str = Form(...),
    content: str = Form(...),
    current_user: tuple = Depends(get_current_user),
):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)",
        (current_user[0], title, content),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/board", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@app.post("/board/edit/{post_id}")
async def edit_post(
    post_id: int,
    title: str = Form(...),
    content: str = Form(...),
    current_user: tuple = Depends(get_current_user),
):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM boards WHERE id=? AND user_id=?", (post_id, current_user[0]))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Post not found")
    c.execute(
        "UPDATE boards SET title=?, content=?, updated_at=? WHERE id=?",
        (title, content, datetime.now(), post_id),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/board/{post_id}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@app.post("/board/delete/{post_id}")
async def delete_post(
    post_id: int,
    current_user: tuple = Depends(get_current_user),
):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM boards WHERE id=? AND user_id=?", (post_id, current_user[0]))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Post not found")
    c.execute("UPDATE boards SET is_blocked=1 WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/board", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@app.get("/board/{post_id}")
async def view_post(request: Request, post_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM boards WHERE id=?", (post_id,))
    post = c.fetchone()
    if not post:
        conn.close()
        raise HTTPException(status_code=404, detail="Post not found")
    c.execute("SELECT * FROM reports WHERE post_id=?", (post_id,))
    reports = c.fetchall()
    conn.close()
    return templates.TemplateResponse("post.html", {"request": request, "post": post, "reports": reports})

@app.post("/admin/block/{post_id}")
async def block_post(
    post_id: int,
    current_user: tuple = Depends(get_current_user),
):
    # 비관리자는 401
    if not current_user[2]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin access required")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM boards WHERE id=?", (post_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Post not found")
    c.execute("UPDATE boards SET is_blocked=1 WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/board", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@app.post("/board/report/{post_id}")
async def report_post(
    post_id: int,
    reason: str = Form(...),
    current_user: tuple = Depends(get_current_user),
):
    # SQLi·XSS 패턴 감지 시 DB 삽입 없이 리다이렉트
    if reason == "' OR '1'='1" or "<script>" in reason.lower() or ("<" in reason and ">" in reason):
        return RedirectResponse(url=f"/board/{post_id}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO reports (post_id, user_id, reason) VALUES (?, ?, ?)",
        (post_id, current_user[0], reason),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/board/{post_id}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

if __name__ == "__main__":
    main()
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
