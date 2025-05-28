from fastapi import FastAPI, Request, Form, HTTPException, Depends
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse
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

@app.get("/")
async def index(request: Request):
    return render_template_string('<h1>Welcome to the Notification System</h1>')

@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    request.session["member_id"] = member_id
    request.session["is_admin"] = False
    return render_template_string('<h1>Logged in as member {member_id}</h1>'.format(member_id=member_id))

@app.post("/notifications/send")
async def send_notification(request: Request, receiver_id: int, title: str, content: str):
    if "member_id" not in request.session:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO notifications (sender_id, receiver_id, title, content) VALUES (?, ?, ?, ?)", (request.session["member_id"], receiver_id, title, content))
    conn.commit()
    conn.close()
    return render_template_string('<h1>Notification sent</h1>')

@app.get("/notifications")
async def list_notifications(request: Request):
    if "member_id" not in request.session:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE receiver_id = ? AND is_deleted = 0 ORDER BY created_at DESC", (request.session["member_id"],))
    notifications = cursor.fetchall()
    conn.close()
    html = '<h1>My Notifications</h1><ul>'
    for notification in notifications:
        if notification['is_read'] == 0:
            html += '<li><strong>{title}</strong> - {content}</li>'.format(title=notification['title'], content=notification['content'])
        else:
            html += '<li>{title} - {content}</li>'.format(title=notification['title'], content=notification['content'])
    html += '</ul>'
    return render_template_string(html)

@app.get("/notifications/{notification_id}")
async def view_notification(request: Request, notification_id: int):
    if "member_id" not in request.session:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE notification_id = ? AND receiver_id = ? AND is_deleted = 0", (notification_id, request.session["member_id"]))
    notification = cursor.fetchone()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE notification_id = ?", (notification_id,))
    conn.commit()
    conn.close()
    html = '<h1>{title}</h1><p>{content}</p><p>Sender: {sender_id}</p>'.format(title=notification['title'], content=notification['content'], sender_id=notification['sender_id'])
    return render_template_string(html)

@app.post("/notifications/delete/{notification_id}")
async def delete_notification(request: Request, notification_id: int):
    if "member_id" not in request.session:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE notification_id = ? AND sender_id = ?", (notification_id, request.session["member_id"]))
    notification = cursor.fetchone()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    cursor.execute("UPDATE notifications SET is_deleted = 1 WHERE notification_id = ?", (notification_id,))
    conn.commit()
    conn.close()
    return render_template_string('<h1>Notification deleted</h1>')

@app.post("/admin/delete_notification/{notification_id}")
async def admin_delete_notification(request: Request, notification_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=401, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE notification_id = ?", (notification_id,))
    notification = cursor.fetchone()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    cursor.execute("UPDATE notifications SET is_deleted = 1 WHERE notification_id = ?", (notification_id,))
    conn.commit()
    conn.close()
    return render_template_string('<h1>Notification deleted</h1>')

@app.get("/admin/notifications")
async def admin_list_notifications(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=401, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE is_deleted = 0")
    notifications = cursor.fetchall()
    conn.close()
    html = '<h1>All Active Notifications</h1><ul>'
    for notification in notifications:
        html += '<li>{title} - {content} - Sender: {sender_id}</li>'.format(title=notification['title'], content=notification['content'], sender_id=notification['sender_id'])
    html += '</ul>'
    return render_template_string(html)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)