from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
import uvicorn
from datetime import datetime

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

def get_db():
    conn = sqlite3.connect("mock_db.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

@app.on_event("startup")
async def startup_event():
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
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            event_date DATE NOT NULL,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'user', 'user@example.com', '<hashed>', 0, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'user')
    ''')
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'admin', 'admin@example.com', '<hashed>', 1, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
    ''')
    conn.execute('''
        INSERT INTO events (creator_id, title, description, event_date, is_deleted)
        SELECT 2, 'Launch Day', 'Site goes live!', '2025-06-01', 0
        WHERE NOT EXISTS (SELECT 1 FROM events WHERE title = 'Launch Day')
    ''')
    conn.commit()
    conn.close()

@app.get("/login/{member_id}")
async def login(request: Request, member_id: str):
    request.session["member_id"] = member_id
    request.session["is_admin"] = member_id == "admin"
    return render_template_string('<html><body><h1>Logged in as {{ member_id }}</h1></body></html>', member_id=member_id)

@app.get("/calendar/create")
async def create_event_form(request: Request):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in first</h1></body></html>')
    return render_template_string('''
        <html>
        <body>
            <h1>Create Event</h1>
            <form method="post" action="/calendar/create">
                Title: <input type="text" name="title"><br>
                Description: <input type="text" name="description"><br>
                Event Date: <input type="date" name="event_date"><br>
                <input type="submit" value="Create">
            </form>
        </body>
        </html>
    ''')

@app.post("/calendar/create")
async def create_event(request: Request, title: str = Form(...), description: str = Form(...), event_date: str = Form(...)):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in first</h1></body></html>')
    conn = get_db()
    conn.execute('''
        INSERT INTO events (creator_id, title, description, event_date, is_deleted)
        VALUES (?, ?, ?, ?, 0)
    ''', (request.session["member_id"], title, description, event_date))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Event created successfully</h1></body></html>')

@app.get("/calendar")
async def list_my_events(request: Request):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in first</h1></body></html>')
    conn = get_db()
    events = conn.execute('''
        SELECT * FROM events WHERE creator_id = ? AND is_deleted = 0 ORDER BY event_date ASC
    ''', (request.session["member_id"],)).fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>My Events</h1>
            <ul>
                {% for event in events %}
                <li>{{ event.title }} - {{ event.event_date }}</li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', events=events)

@app.get("/calendar/{event_id}")
async def view_event(request: Request, event_id: int):
    conn = get_db()
    event = conn.execute('''
        SELECT * FROM events WHERE event_id = ? AND is_deleted = 0
    ''', (event_id,)).fetchone()
    conn.close()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return render_template_string('''
        <html>
        <body>
            <h1>{{ event.title }}</h1>
            <p>{{ event.description }}</p>
            <p>Event Date: {{ event.event_date }}</p>
            <p>Creator: {{ event.creator_id }}</p>
        </body>
        </html>
    ''', event=event)

@app.get("/calendar/edit/{event_id}")
async def edit_event_form(request: Request, event_id: int):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in first</h1></body></html>')
    conn = get_db()
    event = conn.execute('''
        SELECT * FROM events WHERE event_id = ? AND creator_id = ?
    ''', (event_id, request.session["member_id"])).fetchone()
    conn.close()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return render_template_string('''
        <html>
        <body>
            <h1>Edit Event</h1>
            <form method="post" action="/calendar/edit/{{ event_id }}">
                Title: <input type="text" name="title" value="{{ event.title }}"><br>
                Description: <input type="text" name="description" value="{{ event.description }}"><br>
                Event Date: <input type="date" name="event_date" value="{{ event.event_date }}"><br>
                <input type="submit" value="Update">
            </form>
        </body>
        </html>
    ''', event=event)

@app.post("/calendar/edit/{event_id}")
async def edit_event(request: Request, event_id: int, title: str = Form(...), description: str = Form(...), event_date: str = Form(...)):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in first</h1></body></html>')
    conn = get_db()
    conn.execute('''
        UPDATE events SET title = ?, description = ?, event_date = ? WHERE event_id = ? AND creator_id = ?
    ''', (title, description, event_date, event_id, request.session["member_id"]))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Event updated successfully</h1></body></html>')

@app.post("/calendar/delete/{event_id}")
async def delete_event(request: Request, event_id: int):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in first</h1></body></html>')
    conn = get_db()
    conn.execute('''
        UPDATE events SET is_deleted = 1 WHERE event_id = ? AND creator_id = ?
    ''', (event_id, request.session["member_id"]))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Event deleted successfully</h1></body></html>')

@app.post("/admin/delete_event/{event_id}")
async def admin_delete_event(request: Request, event_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return render_template_string('<html><body><h1>Access denied</h1></body></html>')
    conn = get_db()
    conn.execute('''
        UPDATE events SET is_deleted = 1 WHERE event_id = ?
    ''', (event_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Event deleted successfully</h1></body></html>')

@app.get("/admin/events")
async def list_all_events(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return render_template_string('<html><body><h1>Access denied</h1></body></html>')
    conn = get_db()
    events = conn.execute('''
        SELECT * FROM events WHERE is_deleted = 0 ORDER BY event_date ASC
    ''').fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>All Events</h1>
            <ul>
                {% for event in events %}
                <li>{{ event.title }} - {{ event.event_date }}</li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', events=events)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)