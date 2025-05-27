from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
import datetime

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

def get_db():
    conn = sqlite3.connect("mock_db.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    request.session["member_id"] = member_id
    request.session["is_admin"] = False
    return render_template_string("<h1>Logged in as member {{ member_id }}</h1>", member_id=member_id)

@app.post("/notifications/send")
async def send_notification(request: Request, receiver_id: int, title: str, content: str, db: sqlite3.Connection = Depends(get_db)):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    sender_id = request.session["member_id"]
    db.execute("INSERT INTO notifications (sender_id, receiver_id, title, content) VALUES (?, ?, ?, ?)", (sender_id, receiver_id, title, content))
    db.commit()
    return render_template_string("<h1>Notification sent</h1>")

@app.get("/notifications")
async def list_notifications(request: Request, db: sqlite3.Connection = Depends(get_db)):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    member_id = request.session["member_id"]
    notifications = db.execute("SELECT * FROM notifications WHERE receiver_id = ? AND is_deleted = 0 ORDER BY created_at DESC", (member_id,)).fetchall()
    return render_template_string("""
        <h1>Notifications</h1>
        <ul>
            {% for notification in notifications %}
                <li style="font-weight: {% if not notification.is_read %}bold{% endif %}"><a href="/notifications/{{ notification.notification_id }}">{{ notification.title }}</a></li>
            {% endfor %}
        </ul>
    """, notifications=notifications)

@app.get("/notifications/{notification_id}")
async def view_notification(request: Request, notification_id: int, db: sqlite3.Connection = Depends(get_db)):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    member_id = request.session["member_id"]
    notification = db.execute("SELECT * FROM notifications WHERE notification_id = ? AND receiver_id = ? AND is_deleted = 0", (notification_id, member_id)).fetchone()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    db.execute("UPDATE notifications SET is_read = 1 WHERE notification_id = ?", (notification_id,))
    db.commit()
    return render_template_string("""
        <h1>{{ notification.title }}</h1>
        <p>{{ notification.content }}</p>
        <p>Sender: {{ notification.sender_id }}</p>
    """, notification=notification)

@app.post("/notifications/delete/{notification_id}")
async def delete_notification(request: Request, notification_id: int, db: sqlite3.Connection = Depends(get_db)):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    member_id = request.session["member_id"]
    notification = db.execute("SELECT * FROM notifications WHERE notification_id = ? AND sender_id = ? AND is_deleted = 0", (notification_id, member_id)).fetchone()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    db.execute("UPDATE notifications SET is_deleted = 1 WHERE notification_id = ?", (notification_id,))
    db.commit()
    return render_template_string("<h1>Notification deleted</h1>")

@app.post("/admin/delete_notification/{notification_id}")
async def admin_delete_notification(request: Request, notification_id: int, db: sqlite3.Connection = Depends(get_db)):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    notification = db.execute("SELECT * FROM notifications WHERE notification_id = ? AND is_deleted = 0", (notification_id,)).fetchone()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    db.execute("UPDATE notifications SET is_deleted = 1 WHERE notification_id = ?", (notification_id,))
    db.commit()
    return render_template_string("<h1>Notification deleted</h1>")

@app.get("/admin/notifications")
async def admin_list_notifications(request: Request, db: sqlite3.Connection = Depends(get_db)):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    notifications = db.execute("SELECT * FROM notifications WHERE is_deleted = 0 ORDER BY created_at DESC").fetchall()
    return render_template_string("""
        <h1>Admin Notifications</h1>
        <ul>
            {% for notification in notifications %}
                <li><a href="/notifications/{{ notification.notification_id }}">{{ notification.title }}</a></li>
            {% endfor %}
        </ul>
    """, notifications=notifications)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)