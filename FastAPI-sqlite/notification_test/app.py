import sqlite3
from fastapi import FastAPI, Request, Form, HTTPException, Depends, Response
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse
from jinja2 import Template

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

DATABASE = 'mock_db.sqlite3'

@app.on_event("startup")
def create_tables():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0
        )
    ''')
    cursor.execute('''
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
    conn.commit()
    cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)", ('user', 'user@example.com', '<hashed>', 0, 0))
    cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)", ('admin', 'admin@example.com', '<hashed>', 1, 0))
    cursor.execute("INSERT INTO notifications (sender_id, receiver_id, title, content, is_read, is_deleted) VALUES (?, ?, ?, ?, ?, ?)", (2, 1, 'Welcome', 'Hello user!', 0, 0))
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_id(request: Request):
    return request.session.get('member_id')

def is_admin(request: Request):
    return request.session.get('is_admin', False)

@app.get("/login/{member_id}")
async def login(member_id: int, request: Request):
    request.session['member_id'] = member_id
    request.session['is_admin'] = False  # Assuming non-admin by default
    return render_template_string("<html><body>Logged in as member {{ member_id }}</body></html>", member_id=member_id)

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

@app.post("/notifications/send")
async def send_notification(request: Request, receiver_id: int = Form(...), title: str = Form(...), content: str = Form(...)):
    sender_id = get_user_id(request)
    if not sender_id:
        raise HTTPException(status_code=401, detail="You must be logged in to send a notification")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO notifications (sender_id, receiver_id, title, content, is_read, is_deleted) VALUES (?, ?, ?, ?, ?, ?)", (sender_id, receiver_id, title, content, 0, 0))
    conn.commit()
    conn.close()
    return render_template_string("<html><body>Notification sent successfully</body></html>")

@app.get("/notifications")
async def list_notifications(request: Request):
    member_id = get_user_id(request)
    if not member_id:
        raise HTTPException(status_code=401, detail="You must be logged in to view notifications")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE receiver_id = ? AND is_deleted = 0 ORDER BY created_at DESC", (member_id,))
    notifications = cursor.fetchall()
    conn.close()
    html = "<html><body><ul>"
    for notification in notifications:
        is_read = "bold" if notification['is_read'] == 0 else ""
        html += f"<li style='{is_read}'>Title: {notification['title']}, Content: {notification['content']}</li>"
    html += "</ul></body></html>"
    return HTMLResponse(html)

@app.get("/notifications/{notification_id}")
async def view_notification(request: Request, notification_id: int):
    member_id = get_user_id(request)
    if not member_id:
        raise HTTPException(status_code=401, detail="You must be logged in to view notifications")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE notification_id = ? AND receiver_id = ?", (notification_id, member_id))
    notification = cursor.fetchone()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE notification_id = ?", (notification_id,))
    conn.commit()
    conn.close()
    html = f"<html><body>Title: {notification['title']}, Content: {notification['content']}</body></html>"
    return HTMLResponse(html)

@app.post("/notifications/delete/{notification_id}")
async def delete_notification(request: Request, notification_id: int):
    member_id = get_user_id(request)
    if not member_id:
        raise HTTPException(status_code=401, detail="You must be logged in to delete notifications")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE notification_id = ? AND receiver_id = ?", (notification_id, member_id))
    notification = cursor.fetchone()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    cursor.execute("UPDATE notifications SET is_deleted = 1 WHERE notification_id = ?", (notification_id,))
    conn.commit()
    conn.close()
    return render_template_string("<html><body>Notification deleted successfully</body></html>")

@app.post("/admin/delete_notification/{notification_id}")
async def admin_delete_notification(request: Request, notification_id: int):
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE notification_id = ?", (notification_id,))
    notification = cursor.fetchone()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    cursor.execute("UPDATE notifications SET is_deleted = 1 WHERE notification_id = ?", (notification_id,))
    conn.commit()
    conn.close()
    return render_template_string("<html><body>Notification deleted successfully</body></html>")

@app.get("/admin/notifications")
async def list_admin_notifications(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE is_deleted = 0 ORDER BY created_at DESC")
    notifications = cursor.fetchall()
    conn.close()
    html = "<html><body><ul>"
    for notification in notifications:
        html += f"<li>Title: {notification['title']}, Content: {notification['content']}</li>"
    html += "</ul></body></html>"
    return HTMLResponse(html)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)