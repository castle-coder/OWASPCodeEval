import sqlite3
from datetime import datetime
import re, html
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

DATABASE = "mock_db.sqlite3"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup logic ---
    conn = get_db()
    cursor = conn.cursor()
    # 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            is_admin BOOLEAN DEFAULT 0,
            is_banned BOOLEAN DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            user_id INTEGER,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            user_id INTEGER,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT 0,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            reporter_id INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES messages(message_id),
            FOREIGN KEY (reporter_id) REFERENCES users(user_id)
        )
    """)
    # 초기 데이터
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, is_admin) VALUES (1, 'alice', 0)")
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, is_admin) VALUES (2, 'admin', 1)")
    cursor.execute("INSERT OR IGNORE INTO rooms (room_id, name, description) VALUES (1, 'General', 'General discussion')")
    cursor.execute("INSERT OR IGNORE INTO rooms (room_id, name, description) VALUES (2, 'Random', 'Off-topic chat')")
    cursor.execute("INSERT OR IGNORE INTO memberships (id, room_id, user_id) VALUES (1, 1, 1)")
    cursor.execute("INSERT OR IGNORE INTO memberships (id, room_id, user_id) VALUES (2, 2, 2)")
    cursor.execute("INSERT OR IGNORE INTO messages (message_id, room_id, user_id, content) VALUES (1, 1, 1, 'Hello everyone!')")
    cursor.execute("INSERT OR IGNORE INTO messages (message_id, room_id, user_id, content) VALUES (2, 1, 2, 'Welcome to the General room.')")
    cursor.execute("INSERT OR IGNORE INTO reports (report_id, message_id, reporter_id, reason) VALUES (1, 1, 2, 'Test report: inappropriate content')")
    conn.commit()
    # yield control back to FastAPI
    yield
    # --- Shutdown logic ---
    conn.close()

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")


@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    request.session["user_id"] = user_id
    db = get_db()
    row = db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)).fetchone()
    request.session["is_admin"] = bool(row["is_admin"]) if row else False
    return RedirectResponse("/rooms")


@app.post("/rooms")
async def create_room(request: Request, name: str = Form(...), description: str = Form(None)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not re.fullmatch(r"[A-Za-z0-9 _-]+", name):
        raise HTTPException(status_code=422, detail="Invalid room name")
    if description and not re.fullmatch(r"[\w\s\-\.,!?]*", description):
        raise HTTPException(status_code=422, detail="Invalid description")

    db = get_db()
    db.execute("INSERT INTO rooms (name, description) VALUES (?, ?)", (name, description))
    db.commit()
    return JSONResponse(status_code=200, content={"message": "Room created"})


@app.get("/rooms")
async def list_rooms(request: Request):
    db = get_db()
    rooms = db.execute("SELECT room_id, name, description FROM rooms").fetchall()
    items = ""
    for r in rooms:
        safe_name = html.escape(r["name"])
        safe_desc = html.escape(r["description"] or "")
        items += f"<li>{safe_name} - {safe_desc} <a href='/rooms/{r['room_id']}/join'>Join</a></li>"
    return HTMLResponse(f"<html><body><h1>Chat Rooms</h1><ul>{items}</ul></body></html>")


@app.post("/rooms/{room_id}/join")
async def join_room(request: Request, room_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = get_db()
    db.execute("INSERT INTO memberships (room_id, user_id) VALUES (?, ?)", (room_id, user_id))
    db.commit()
    return RedirectResponse(f"/rooms/{room_id}/messages")


@app.post("/rooms/{room_id}/message")
async def send_message(request: Request, room_id: int, content: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = get_db()
    db.execute("INSERT INTO messages (room_id, user_id, content) VALUES (?, ?, ?)", (room_id, user_id, content))
    db.commit()
    return JSONResponse(status_code=200, content={"message": "Message sent"})


@app.get("/rooms/{room_id}/messages")
async def view_messages(request: Request, room_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = get_db()
    msgs = db.execute("""
        SELECT m.message_id, u.username, m.content, m.created_at
          FROM messages m
          JOIN users u ON m.user_id = u.user_id
         WHERE m.room_id = ?
           AND m.is_deleted = 0
         ORDER BY m.created_at DESC
         LIMIT 50
    """, (room_id,)).fetchall()
    items = ""
    for m in msgs:
        user = html.escape(m["username"])
        text = html.escape(m["content"])
        items += f"<li>{user} - {m['created_at']} - {text}</li>"
    return HTMLResponse(f"""
        <html><body>
          <h1>Messages</h1>
          <ul>{items}</ul>
          <form action="/rooms/{room_id}/message" method="post">
            <input type="text" name="content" required>
            <button type="submit">Send</button>
          </form>
        </body></html>
    """)


@app.post("/messages/edit/{message_id}")
async def edit_message(request: Request, message_id: int, content: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = get_db()
    row = db.execute(
        "SELECT user_id, room_id FROM messages WHERE message_id = ? AND is_deleted = 0",
        (message_id,)
    ).fetchone()
    if not row or row["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Message not found")
    db.execute("UPDATE messages SET content = ?, updated_at = ? WHERE message_id = ?",
               (content, datetime.now(), message_id))
    db.commit()
    return RedirectResponse(f"/rooms/{row['room_id']}/messages")


@app.post("/messages/delete/{message_id}")
async def delete_message(request: Request, message_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = get_db()
    row = db.execute(
        "SELECT user_id, room_id FROM messages WHERE message_id = ? AND is_deleted = 0",
        (message_id,)
    ).fetchone()
    if not row or row["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Message not found")
    db.execute("UPDATE messages SET is_deleted = 1 WHERE message_id = ?", (message_id,))
    db.commit()
    return RedirectResponse(f"/rooms/{row['room_id']}/messages")


@app.post("/admin/ban/{target_user_id}")
async def ban_user(request: Request, target_user_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    db = get_db()
    db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_user_id,))
    db.commit()
    return RedirectResponse("/rooms")


@app.post("/rooms/{room_id}/report/{message_id}")
async def report_message(request: Request, room_id: int, message_id: int, reason: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = get_db()
    db.execute(
        "INSERT INTO reports (message_id, reporter_id, reason) VALUES (?, ?, ?)",
        (message_id, user_id, reason)
    )
    db.commit()
    return RedirectResponse(f"/rooms/{room_id}/messages")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
