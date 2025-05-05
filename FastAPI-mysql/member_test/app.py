from fastapi import FastAPI, Request, Form, HTTPException, status, Depends
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext
import sqlite3

app = FastAPI()
# Session middleware so request.session works
app.add_middleware(SessionMiddleware, secret_key="your-secret-key", max_age=3600, same_site="lax")

# DB setup
DATABASE = "mock_db.sqlite3"
conn = sqlite3.connect(DATABASE, check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked BOOLEAN DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(post_id) REFERENCES boards(id),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    # dummy users
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, email, password, is_admin, is_deleted) VALUES (1,'user','user@example.com','hashed',0,0)")
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, email, password, is_admin, is_deleted) VALUES (2,'admin','admin@example.com','hashed',1,0)")
    # dummy boards
    cursor.execute("INSERT OR IGNORE INTO boards (id, user_id, title, content) VALUES (1,1,'First Post','This is the first post.')")
    cursor.execute("INSERT OR IGNORE INTO boards (id, user_id, title, content) VALUES (2,2,'Admin Post','This post was written by an admin.')")
    # dummy report
    cursor.execute("INSERT OR IGNORE INTO reports (report_id, post_id, user_id, reason) VALUES (1,2,1,'Test report entry')")
    conn.commit()

init_db()

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_current_user(request: Request):
    uid = request.session.get("member_id")
    if not uid:
        return None
    cursor.execute(
        "SELECT user_id, username, email, is_admin "
        "FROM users WHERE user_id=? AND is_deleted=0",
        (uid,)
    )
    return cursor.fetchone()

def require_user(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user

def sanitize(text: str):
    return not any(tok in text for tok in ("<", ";", "--"))

# Now create_post enforces auth first, so unauthenticated => 401
@app.post("/board")
def create_post(
    user=Depends(require_user),
    title: str = Form(...),
    content: str = Form(...)
):
    if not sanitize(title) or not sanitize(content):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    cursor.execute(
        "INSERT INTO boards (user_id, title, content) VALUES (?,?,?)",
        (user[0], title, content)
    )
    conn.commit()
    return {"message": "Post created"}

@app.post("/board/edit/{post_id}")
def edit_post(
    post_id: int,
    user=Depends(require_user),
    title: str = Form(...),
    content: str = Form(...)
):
    cursor.execute("SELECT user_id FROM boards WHERE id=?", (post_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if row[0] != user[0]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if not sanitize(title) or not sanitize(content):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    cursor.execute(
        "UPDATE boards SET title=?, content=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (title, content, post_id)
    )
    conn.commit()
    return {"message": "Post updated"}

@app.post("/board/delete/{post_id}")
def delete_post(
    post_id: int,
    user=Depends(require_user)
):
    cursor.execute("SELECT user_id FROM boards WHERE id=?", (post_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if row[0] != user[0]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    cursor.execute("DELETE FROM boards WHERE id=?", (post_id,))
    conn.commit()
    return {"message": "Post deleted"}

@app.post("/admin/block/{post_id}")
def block_post(
    post_id: int,
    user=Depends(require_user)
):
    if not user[3]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    cursor.execute("SELECT id FROM boards WHERE id=?", (post_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    cursor.execute("UPDATE boards SET is_blocked=1 WHERE id=?", (post_id,))
    conn.commit()
    return {"message": "Post blocked"}

@app.post("/board/report/{post_id}")
def report_post(
    post_id: int,
    user=Depends(require_user),
    reason: str = Form(...)
):
    if not sanitize(reason):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    cursor.execute("SELECT id FROM boards WHERE id=?", (post_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    cursor.execute(
        "INSERT INTO reports (post_id, user_id, reason) VALUES (?,?,?)",
        (post_id, user[0], reason)
    )
    conn.commit()
    return {"message": "Reported"}

@app.get("/login/{member_id}")
def login(member_id: int, request: Request):
    request.session["member_id"] = member_id
    request.session["is_admin"] = bool(get_current_user(request)[3])
    return {"message": "Logged in"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)
