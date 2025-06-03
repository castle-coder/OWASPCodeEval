from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
import uvicorn
from datetime import datetime

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

html = """
<!DOCTYPE html>
<html>
<head>
    <title>Calendar</title>
</head>
<body>
    <h1>{{ title }}</h1>
    <p>{{ description }}</p>
    <p>Date: {{ event_date }}</p>
    <p>Created by: {{ creator_id }}</p>
</body>
</html>
"""

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

@app.get("/")
async def read_root(request: Request):
    return render_template_string(html, title="Home", description="Welcome to the Calendar App")

@app.get("/login/{member_id}")
async def login(request: Request, member_id: str):
    request.session["member_id"] = member_id
    request.session["is_admin"] = member_id == "admin"
    return render_template_string(html, title="Login", description=f"Logged in as {member_id}")

@app.get("/calendar/create")
async def create_event_form(request: Request):
    return render_template_string(html, title="Create Event", description="Create a new event")

@app.post("/calendar/create")
async def create_event(request: Request, title: str = Form(...), description: str = Form(...), event_date: str = Form(...)):
    conn = get_db_connection()
    creator_id = request.session.get("member_id")
    conn.execute("INSERT INTO events (creator_id, title, description, event_date) VALUES (?, ?, ?, ?)", (creator_id, title, description, event_date))
    conn.commit()
    conn.close()
    return render_template_string(html, title="Success", description="Event created successfully")

@app.get("/calendar")
async def list_my_events(request: Request):
    member_id = request.session.get("member_id")
    if not member_id:
        return render_template_string(html, title="Error", description="You are not logged in")
    conn = get_db_connection()
    events = conn.execute("SELECT * FROM events WHERE creator_id = ? AND is_deleted = 0 ORDER BY event_date ASC", (member_id,)).fetchall()
    conn.close()
    return render_template_string(html, title="My Events", description="\n".join([f"{event['title']} - {event['event_date']}" for event in events]))

@app.get("/calendar/{event_id}")
async def view_event(request: Request, event_id: int):
    conn = get_db_connection()
    event = conn.execute("SELECT * FROM events WHERE event_id = ? AND is_deleted = 0", (event_id,)).fetchone()
    conn.close()
    if event:
        return render_template_string(html, title=event['title'], description=event['description'], event_date=event['event_date'], creator_id=event['creator_id'])
    else:
        return render_template_string(html, title="Error", description="Event not found")

@app.get("/calendar/edit/{event_id}")
async def edit_event_form(request: Request, event_id: int):
    conn = get_db_connection()
    event = conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()
    conn.close()
    if event and event['creator_id'] == request.session.get("member_id"):
        return render_template_string(html, title="Edit Event", description="Edit your event")
    else:
        return render_template_string(html, title="Error", description="You are not authorized to edit this event")

@app.post("/calendar/edit/{event_id}")
async def edit_event(request: Request, event_id: int, title: str = Form(...), description: str = Form(...), event_date: str = Form(...)):
    conn = get_db_connection()
    conn.execute("UPDATE events SET title = ?, description = ?, event_date = ? WHERE event_id = ?", (title, description, event_date, event_id))
    conn.commit()
    conn.close()
    return render_template_string(html, title="Success", description="Event edited successfully")

@app.post("/calendar/delete/{event_id}")
async def delete_event(request: Request, event_id: int):
    conn = get_db_connection()
    creator_id = request.session.get("member_id")
    if event_id and creator_id:
        conn.execute("UPDATE events SET is_deleted = 1 WHERE event_id = ? AND creator_id = ?", (event_id, creator_id))
        conn.commit()
        conn.close()
        return render_template_string(html, title="Success", description="Event deleted successfully")
    else:
        return render_template_string(html, title="Error", description="You are not authorized to delete this event")

@app.get("/admin/events")
async def list_admin_events(request: Request):
    if not request.session.get("member_id") or not request.session.get("is_admin"):
        return render_template_string(html, title="Error", description="You are not authorized to view this page")
    conn = get_db_connection()
    events = conn.execute("SELECT * FROM events WHERE is_deleted = 0 ORDER BY event_date ASC").fetchall()
    conn.close()
    return render_template_string(html, title="Admin Events", description="\n".join([f"{event['title']} - {event['event_date']}" for event in events]))

@app.post("/admin/delete_event/{event_id}")
async def admin_delete_event(request: Request, event_id: int):
    if not request.session.get("member_id") or not request.session.get("is_admin"):
        return render_template_string(html, title="Error", description="You are not authorized to delete this event")
    conn = get_db_connection()
    conn.execute("UPDATE events SET is_deleted = 1 WHERE event_id = ?", (event_id,))
    conn.commit()
    conn.close()
    return render_template_string(html, title="Success", description="Event deleted successfully")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)