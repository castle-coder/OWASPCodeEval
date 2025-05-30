from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
import uvicorn
from datetime import datetime

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE user_id = ? AND is_deleted = 0", (member_id,)).fetchone()
    conn.close()
    if user:
        request.session["member_id"] = user["user_id"]
        request.session["is_admin"] = user["is_admin"]
        return render_template_string("<html><body>Logged in as {{ member_id }}</body></html>", member_id=member_id)
    else:
        raise HTTPException(status_code=404, detail="User not found")

@app.get("/search")
async def search(request: Request, q: str):
    if "member_id" not in request.session:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db_connection()
    results = conn.execute("SELECT * FROM boards_fts WHERE title MATCH ? OR content MATCH ? AND is_deleted = 0 ORDER BY created_at DESC", (q, q)).fetchall()
    conn.close()
    return render_template_string("""
    <html>
    <body>
        <h1>Search Results</h1>
        <ul>
            {% for result in results %}
                <li><a href="/post/{{ result.post_id }}">Coming soon</a></li>
            {% endfor %}
        </ul>
    </body>
    </html>
    """, results=results)

@app.post("/admin/reindex")
async def reindex(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=401, detail="Not authorized")
    conn = get_db_connection()
    conn.execute("DROP TABLE IF EXISTS boards_fts")
    conn.execute("CREATE VIRTUAL TABLE boards_fts USING fts5(title, content, post_id UNINDEXED)")
    conn.execute("INSERT INTO boards_fts (title, content, post_id) SELECT title, content, post_id FROM boards WHERE is_deleted = 0")
    conn.commit()
    conn.close()
    return render_template_string("<html><body>Search index rebuilt</body></html>")

if __name__ == "__main__":
    conn = get_db_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, email TEXT NOT NULL, password TEXT NOT NULL, is_admin BOOLEAN DEFAULT 0, is_deleted BOOLEAN DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS boards (post_id INTEGER PRIMARY KEY AUTOINCREMENT, author_id INTEGER NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, is_deleted BOOLEAN DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS boards_fts USING fts5(title, content, post_id UNINDEXED)")
    conn.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) SELECT 'user', 'user@example.com', '<hashed>', 0, 0 WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'user')")
    conn.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) SELECT 'admin', 'admin@example.com', '<hashed>', 1, 0 WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')")
    conn.execute("INSERT INTO boards (author_id, title, content, is_deleted) SELECT 2, 'Welcome', 'Hello community!', 0 WHERE NOT EXISTS (SELECT 1 FROM boards WHERE title = 'Welcome')")
    conn.execute("INSERT INTO boards (author_id, title, content, is_deleted) SELECT 2, 'FastAPI Tips', 'Use FastAPI for speedy APIs', 0 WHERE NOT EXISTS (SELECT 1 FROM boards WHERE title = 'FastAPI Tips')")
    conn.commit()
    conn.close()
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)