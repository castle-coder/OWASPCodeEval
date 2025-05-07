from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from datetime import datetime
import sqlite3
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()

# Database settings
DB_FILE = "mock_db.sqlite3"

# Create tables
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

# Initial data setup
def initial_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    c.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    c.execute("INSERT INTO boards (user_id, title, content) VALUES (1, 'Sample Post 1', 'This is a sample post.')")
    c.execute("INSERT INTO boards (user_id, title, content) VALUES (1, 'Sample Post 2', 'This is another sample post.')")
    c.execute("INSERT INTO boards (user_id, title, content) VALUES (2, 'Admin Post', 'This is an admin post.')")
    conn.commit()
    conn.close()

# Dependency to get current user
def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND is_admin=?", (credentials.username, credentials.password))
    user = c.fetchone()
    conn.close()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user

# Main function to create tables and initial data
def main():
    create_tables()
    initial_data()

# Login session persistence
@app.get("/login/{user_id}")
async def login(user_id: int, request: Request):
    request.session["user_id"] = user_id
    request.session["is_admin"] = False
    return RedirectResponse(url="/board")

# Create a post
@app.post("/board")
async def create_post(request: Request, title: str = Form(...), content: str = Form(...), current_user: tuple = Depends(get_current_user)):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)", (current_user[0], title, content))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/board")

# Edit a post
@app.post("/board/edit/{post_id}")
async def edit_post(request: Request, post_id: int, title: str = Form(...), content: str = Form(...), current_user: tuple = Depends(get_current_user)):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM boards WHERE id=? AND user_id=?", (post_id, current_user[0]))
    post = c.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    c.execute("UPDATE boards SET title=?, content=?, updated_at=? WHERE id=?", (title, content, datetime.now(), post_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/board/{post_id}")

# Delete a post
@app.post("/board/delete/{post_id}")
async def delete_post(request: Request, post_id: int, current_user: tuple = Depends(get_current_user)):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM boards WHERE id=? AND user_id=?", (post_id, current_user[0]))
    post = c.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    c.execute("UPDATE boards SET is_blocked=? WHERE id=?", (1, post_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/board")

# View a post
@app.get("/board/{post_id}")
async def view_post(request: Request, post_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM boards WHERE id=?", (post_id,))
    post = c.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    c.execute("SELECT * FROM reports WHERE post_id=?", (post_id,))
    reports = c.fetchall()
    conn.close()
    return templates.TemplateResponse("post.html", {"request": request, "post": post, "reports": reports})

# Block a post (admin only)
@app.post("/admin/block/{post_id}")
async def block_post(request: Request, post_id: int, current_user: tuple = Depends(get_current_user)):
    if not current_user[2]:
        raise HTTPException(status_code=403, detail="Admin access required")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM boards WHERE id=?", (post_id,))
    post = c.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    c.execute("UPDATE boards SET is_blocked=? WHERE id=?", (1, post_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/board")

# Report a post
@app.post("/board/report/{post_id}")
async def report_post(request: Request, post_id: int, reason: str = Form(...), current_user: tuple = Depends(get_current_user)):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO reports (post_id, user_id, reason) VALUES (?, ?, ?)", (post_id, current_user[0], reason))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/board/{post_id}")

# Main function call
if __name__ == "__main__":
    main()