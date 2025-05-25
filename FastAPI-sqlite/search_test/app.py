from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import sqlite3
from datetime import datetime

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DATABASE = 'mock_db.sqlite3'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
async def startup_event():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT,
            is_admin  BOOLEAN
        );
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            title       TEXT,
            content     TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
    ''')
    conn.execute('''
        INSERT INTO users (username, is_admin) VALUES ('user1', 0), ('user2', 0);
    ''')
    conn.execute('''
        INSERT INTO posts (user_id, title, content) VALUES (1, 'Post 1', 'Content of post 1'), (1, 'Post 2', 'Content of post 2'), (2, 'Post 3', 'Content of post 3');
    ''')
    conn.commit()
    conn.close()

@app.middleware("http")
async def add_session_middleware(request: Request, call_next):
    response = await call_next(request)
    return response

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    last_query = request.session.get('last_query', '')
    return templates.TemplateResponse("home.html", {"request": request, "last_query": last_query})

@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = Query(...), author_id: int = None, date_from: str = None, date_to: str = None, page: int = 1):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM posts WHERE title LIKE ? OR content LIKE ?"
    params = ('%' + q + '%', '%' + q + '%')
    if author_id:
        query += " AND user_id = ?"
        params += (author_id,)
    if date_from:
        query += " AND created_at >= ?"
        params += (datetime.strptime(date_from, '%Y-%m-%d'),)
    if date_to:
        query += " AND created_at <= ?"
        params += (datetime.strptime(date_to, '%Y-%m-%d'),)
    query += " ORDER BY created_at DESC LIMIT 10 OFFSET ?"
    params += ((page - 1) * 10,)
    cursor.execute(query, params)
    posts = cursor.fetchall()
    request.session['last_query'] = q
    conn.close()
    return templates.TemplateResponse("search.html", {"request": request, "posts": posts, "q": q, "author_id": author_id, "date_from": date_from, "date_to": date_to, "page": page})

@app.get("/posts/{post_id}", response_class=HTMLResponse)
async def view_post(request: Request, post_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
    post = cursor.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    conn.close()
    return templates.TemplateResponse("post.html", {"request": request, "post": post})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)