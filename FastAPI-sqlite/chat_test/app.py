from fastapi import FastAPI, Request, HTTPException, Form, Depends, Response
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from datetime import datetime
import sqlite3

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

DATABASE = "mock_db.sqlite3"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
def startup():
    conn = get_db()
    cursor = conn.cursor()
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
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('alice', 0)")
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    cursor.execute("INSERT INTO rooms (name, description) VALUES ('General', 'General discussion')")
    cursor.execute("INSERT INTO rooms (name, description) VALUES ('Random', 'Off-topic chat')")
    cursor.execute("INSERT INTO memberships (room_id, user_id) VALUES (1, 1)")
    cursor.execute("INSERT INTO memberships (room_id, user_id) VALUES (2, 2)")
    cursor.execute("INSERT INTO messages (room_id, user_id, content) VALUES (1, 1, 'Hello everyone!')")
    cursor.execute("INSERT INTO messages (room_id, user_id, content) VALUES (1, 2, 'Welcome to the General room.')")
    cursor.execute("INSERT INTO reports (message_id, reporter_id, reason) VALUES (1, 2, 'Test report: inappropriate content')")
    conn.commit()

@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    request.session["user_id"] = user_id
    request.session["username"] = "alice"  # Assuming username is always 'alice' for simplicity
    return RedirectResponse("/rooms")

@app.post("/rooms")
async def create_room(request: Request, name: str = Form(...), description: str = Form(None)):
    user_id = request.session.get("user_id")
    if not user_id:
        return HTMLResponse("You must be logged in to create a room.")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO rooms (name, description) VALUES (?, ?)", (name, description))
    conn.commit()
    return RedirectResponse("/rooms")

@app.get("/rooms")
async def list_rooms(request: Request):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT room_id, name, description FROM rooms")
    rooms = cursor.fetchall()
    html = "<h1>Chat Rooms</h1><ul>"
    for room in rooms:
        html += f"<li>{room['name']} - {room['description']} <a href='/rooms/{room['room_id']}/join'>Join</a></li>"
    html += "</ul>"
    return HTMLResponse(html)

@app.post("/rooms/{room_id}/join")
async def join_room(request: Request, room_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        return HTMLResponse("You must be logged in to join a room.")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO memberships (room_id, user_id) VALUES (?, ?)", (room_id, user_id))
    conn.commit()
    return RedirectResponse(f"/rooms/{room_id}/messages")

@app.post("/rooms/{room_id}/message")
async def send_message(request: Request, room_id: int, content: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        return HTMLResponse("You must be logged in to send a message.")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (room_id, user_id, content) VALUES (?, ?, ?)", (room_id, user_id, content))
    conn.commit()
    return RedirectResponse(f"/rooms/{room_id}/messages")

@app.get("/rooms/{room_id}/messages")
async def view_messages(request: Request, room_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        return HTMLResponse("You must be logged in to view messages.")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT messages.message_id, users.username, messages.content, messages.created_at FROM messages JOIN users ON messages.user_id = users.user_id WHERE messages.room_id = ? ORDER BY messages.created_at DESC LIMIT 50", (room_id,))
    messages = cursor.fetchall()
    html = "<h1>Messages</h1><ul>"
    for message in messages:
        html += f"<li>{message['username']} - {message['created_at']}: {message['content']}</li>"
    html += "</ul>"
    return HTMLResponse(html)

@app.post("/messages/edit/{message_id}")
async def edit_message(request: Request, message_id: int, content: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        return HTMLResponse("You must be logged in to edit a message.")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM messages WHERE message_id = ?", (message_id,))
    original_user_id = cursor.fetchone()
    if original_user_id and original_user_id['user_id'] != user_id:
        return HTMLResponse("You cannot edit messages from other users.")
    cursor.execute("UPDATE messages SET content = ?, updated_at = ? WHERE message_id = ?", (content, datetime.now(), message_id))
    conn.commit()
    return RedirectResponse(f"/rooms/{message_id}/messages")

@app.post("/messages/delete/{message_id}")
async def delete_message(request: Request, message_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        return HTMLResponse("You must be logged in to delete a message.")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM messages WHERE message_id = ?", (message_id,))
    original_user_id = cursor.fetchone()
    if original_user_id and original_user_id['user_id'] != user_id:
        return HTMLResponse("You cannot delete messages from other users.")
    cursor.execute("UPDATE messages SET is_deleted = 1 WHERE message_id = ?", (message_id,))
    conn.commit()
    return RedirectResponse(f"/rooms/{message_id}/messages")

@app.post("/admin/ban/{user_id}")
async def ban_user(request: Request, user_id: int):
    user_id = request.session.get("user_id")
    if not user_id or not request.session.get("is_admin"):
        return HTMLResponse("You must be an admin to ban a user.")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    return RedirectResponse("/rooms")

@app.post("/rooms/{room_id}/report/{message_id}")
async def report_message(request: Request, room_id: int, message_id: int, reason: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        return HTMLResponse("You must be logged in to report a message.")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reports (message_id, reporter_id, reason) VALUES (?, ?, ?)", (message_id, user_id, reason))
    conn.commit()
    return RedirectResponse(f"/rooms/{room_id}/messages")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)