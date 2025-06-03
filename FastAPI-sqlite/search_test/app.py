import sqlite3
from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

# Initialize database and insert dummy data
def init_db():
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    
    cursor.executescript('''
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0
        );
        
        CREATE TABLE boards (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE VIRTUAL TABLE boards_fts USING FTS5(title, content, post_id UNINDEXED);
        
        INSERT INTO users (username, email, password, is_admin, is_deleted) 
        VALUES ('user', 'user@example.com', '<hashed>', 0, 0),
               ('admin', 'admin@example.com', '<hashed>', 1, 0);
        
        INSERT INTO boards (author_id, title, content, is_deleted) 
        VALUES (2, 'Welcome', 'Hello community!', 0),
               (2, 'FastAPI Tips', 'Use FastAPI for speedy APIs', 0);
        
        INSERT INTO boards_fts (title, content, post_id) 
        SELECT title, content, post_id FROM boards;
    ''')
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/login/{member_id}")
async def login(request: Request, member_id: str):
    request.session["member_id"] = member_id
    request.session["is_admin"] = False
    if member_id == "admin":
        request.session["is_admin"] = True
    return render_template_string('<html><body>Logged in as {{ member_id }}</body></html>', member_id=member_id)

@app.get("/search")
async def search(request: Request, q: str):
    if "member_id" not in request.session:
        return render_template_string('<html><body>Please log in first</body></html>')
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    cursor.execute("SELECT post_id, title, content FROM boards_fts WHERE title MATCH ? OR content MATCH ?", (q, q))
    posts = cursor.fetchall()
    conn.close()
    html = '<html><body><ul>'
    for post in posts:
        html += f'<li><a href="/post/{post[0]}">{post[1]}</a></li>'
    html += '</ul></body></html>'
    return render_template_string(html)

@app.post("/admin/reindex")
async def reindex(request: Request):
    if not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS boards_fts")
    cursor.executescript('''
        CREATE VIRTUAL TABLE boards_fts USING FTS5(title, content, post_id UNINDEXED);
        INSERT INTO boards_fts (title, content, post_id) 
        SELECT title, content, post_id FROM boards;
    ''')
    conn.commit()
    conn.close()
    return render_template_string('<html><body>Search index rebuilt</body></html>')

@app.get("/post/{post_id}")
async def post(request: Request, post_id: int):
    return render_template_string('<html><body>Coming soon</body></html>')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)