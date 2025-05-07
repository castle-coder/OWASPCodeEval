from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates
import sqlite3
from datetime import datetime

app = FastAPI()

# Middleware for session management
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

# Database configuration
DATABASE = "mock_db.sqlite3"

# Create tables and insert test rows
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            is_admin BOOLEAN
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_cancelled BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rsvps (
            rsvp_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            user_id INTEGER,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('alice', 0)")
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    cursor.execute("INSERT INTO events (user_id, title, description, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
                   (1, 'Meeting', 'Team sync-up', '2025-05-10 10:00:00', '2025-05-10 11:00:00'))
    cursor.execute("INSERT INTO events (user_id, title, description, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
                   (2, 'Admin Review', 'Quarterly review', '2025-05-15 14:00:00', '2025-05-15 15:30:00'))
    cursor.execute("INSERT INTO rsvps (event_id, user_id, status) VALUES (?, ?, ?)", (1, 2, 'yes'))
    conn.commit()
    conn.close()

# Initialize the database
init_db()

# Templates
templates = Jinja2Templates(directory="templates")

# Basic authentication
security = HTTPBasic()

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (credentials.username,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user

@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    request.session["user_id"] = user_id
    request.session["is_admin"] = False
    return RedirectResponse(url="/calendar")

@app.post("/calendar")
async def create_event(request: Request, title: str = Form(...), description: str = Form(...), start_time: str = Form(...), end_time: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO events (user_id, title, description, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
                   (user_id, title, description, start_time, end_time))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/calendar")

@app.post("/calendar/edit/{event_id}")
async def edit_event(request: Request, event_id: int, title: str = Form(...), description: str = Form(...), start_time: str = Form(...), end_time: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ? AND user_id = ?", (event_id, user_id))
    event = cursor.fetchone()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    cursor.execute("UPDATE events SET title = ?, description = ?, start_time = ?, end_time = ? WHERE id = ?",
                   (title, description, start_time, end_time, event_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/calendar")

@app.post("/calendar/delete/{event_id}")
async def delete_event(request: Request, event_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ? AND user_id = ?", (event_id, user_id))
    event = cursor.fetchone()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    cursor.execute("UPDATE events SET is_cancelled = 1 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/calendar")

@app.get("/calendar")
async def view_events(request: Request):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE is_cancelled = 0")
    events = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("events.html", {"request": request, "events": events})

@app.get("/calendar/{event_id}")
async def view_event(request: Request, event_id: int):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    cursor.execute("SELECT * FROM rsvps WHERE event_id = ?", (event_id,))
    rsvps = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("event.html", {"request": request, "event": event, "rsvps": rsvps})

@app.post("/calendar/rsvp/{event_id}")
async def rsvp_to_event(request: Request, event_id: int, status: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO rsvps (event_id, user_id, status) VALUES (?, ?, ?)", (event_id, user_id, status))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/calendar/{event_id}")

@app.post("/admin/cancel/{event_id}")
async def cancel_event(request: Request, event_id: int):
    user_id = request.session.get("user_id")
    if not user_id or not request.session.get("is_admin"):
        raise HTTPException(status_code=401, detail="Not authorized")
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET is_cancelled = 1 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/calendar")

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)