from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
import datetime

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

def get_db():
    conn = sqlite3.connect("mock_db.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
def startup():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_read BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute("INSERT INTO users (username, email, password, is_admin) VALUES ('user', 'user@example.com', '<hashed>', 0)")
    conn.execute("INSERT INTO users (username, email, password, is_admin) VALUES ('admin', 'admin@example.com', '<hashed>', 1)")
    conn.execute("INSERT INTO notifications (sender_id, receiver_id, title, content) VALUES (2, 1, 'Welcome', 'Hello user!')")
    conn.commit()
    conn.close()

@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    request.session["member_id"] = member_id
    request.session["is_admin"] = False
    return render_template_string('<html><body><h1>Logged in as member {{ member_id }}</h1></body></html>', member_id=member_id)

@app.post("/notifications/send")
async def send_notification(request: Request, receiver_id: int = Form(...), title: str = Form(...), content: str = Form(...)):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    conn.execute("INSERT INTO notifications (sender_id, receiver_id, title, content) VALUES (?, ?, ?, ?)", (request.session["member_id"], receiver_id, title, content))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Notification sent</h1></body></html>')

@app.get("/notifications")
async def list_notifications(request: Request):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    notifications = conn.execute("SELECT * FROM notifications WHERE receiver_id = ? AND is_deleted = 0 ORDER BY created_at DESC", (request.session["member_id"],)).fetchall()
    conn.close()
    html = '<html><body><h1>My Notifications</h1><ul>'
    for notification in notifications:
        if notification['is_read'] == 0:
            html += f'<li><strong>{notification["title"]}</strong> - {notification["content"]}</li>'
        else:
            html += f'<li>{notification["title"]} - {notification["content"]}</li>'
    html += '</ul></body></html>'
    return render_template_string(html)

@app.get("/notifications/{notification_id}")
async def view_notification(request: Request, notification_id: int):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    notification = conn.execute("SELECT * FROM notifications WHERE notification_id = ? AND receiver_id = ? AND is_deleted = 0", (notification_id, request.session["member_id"])).fetchone()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    conn.execute("UPDATE notifications SET is_read = 1 WHERE notification_id = ?", (notification_id,))
    conn.commit()
    conn.close()
    html = f'<html><body><h1>{notification["title"]}</h1><p>{notification["content"]}</p><p>Sender: {notification["sender_id"]}</p></body></html>'
    return render_template_string(html)

@app.post("/notifications/delete/{notification_id}")
async def delete_notification(request: Request, notification_id: int):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    notification = conn.execute("SELECT * FROM notifications WHERE notification_id = ? AND sender_id = ?", (notification_id, request.session["member_id"])).fetchone()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    conn.execute("UPDATE notifications SET is_deleted = 1 WHERE notification_id = ?", (notification_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Notification deleted</h1></body></html>')

@app.post("/admin/delete_notification/{notification_id}")
async def admin_delete_notification(request: Request, notification_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    conn = get_db()
    notification = conn.execute("SELECT * FROM notifications WHERE notification_id = ?", (notification_id,)).fetchone()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    conn.execute("UPDATE notifications SET is_deleted = 1 WHERE notification_id = ?", (notification_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Notification deleted</h1></body></html>')

@app.get("/admin/notifications")
async def admin_list_notifications(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    conn = get_db()
    notifications = conn.execute("SELECT * FROM notifications WHERE is_deleted = 0").fetchall()
    conn.close()
    html = '<html><body><h1>All Notifications</h1><ul>'
    for notification in notifications:
        html += f'<li>{notification["title"]} - {notification["content"]} - Sender: {notification["sender_id"]}</li>'
    html += '</ul></body></html>'
    return render_template_string(html)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)