from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates
from sqlite3 import connect, Row
from datetime import datetime
import uvicorn

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

templates = Jinja2Templates(directory="templates")

DATABASE = "mock_db.sqlite3"

def get_db():
    conn = connect(DATABASE)
    conn.row_factory = Row
    return conn

@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    request.session["user_id"] = user_id
    request.session["is_admin"] = user_id == 2
    return RedirectResponse(url="/calendar")

@app.post("/calendar")
async def create_event(request: Request, title: str = Form(...), description: str = Form(...), start_time: str = Form(...), end_time: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO events (user_id, title, description, start_time, end_time) VALUES (?, ?, ?, ?, ?)", (user_id, title, description, start_time, end_time))
    conn.commit()
    return RedirectResponse(url="/calendar")

@app.post("/calendar/edit/{event_id}")
async def edit_event(request: Request, event_id: int, title: str = Form(...), description: str = Form(...), start_time: str = Form(...), end_time: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM events WHERE id = ?", (event_id,))
    event_user_id = cursor.fetchone()[0]
    if event_user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    cursor.execute("UPDATE events SET title = ?, description = ?, start_time = ?, end_time = ? WHERE id = ?", (title, description, start_time, end_time, event_id))
    conn.commit()
    return RedirectResponse(url="/calendar")

@app.post("/calendar/delete/{event_id}")
async def delete_event(request: Request, event_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM events WHERE id = ?", (event_id,))
    event_user_id = cursor.fetchone()[0]
    if event_user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    cursor.execute("UPDATE events SET is_cancelled = 1 WHERE id = ?", (event_id,))
    conn.commit()
    return RedirectResponse(url="/calendar")

@app.get("/calendar")
async def view_events(request: Request):
    user_id = request.session.get("user_id")
    is_admin = request.session.get("is_admin")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE is_cancelled = 0")
    events = cursor.fetchall()
    return templates.TemplateResponse("events.html", {"request": request, "events": events, "user_id": user_id, "is_admin": is_admin})

@app.get("/calendar/{event_id}")
async def view_event(request: Request, event_id: int):
    user_id = request.session.get("user_id")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    cursor.execute("SELECT * FROM rsvps WHERE event_id = ?", (event_id,))
    rsvps = cursor.fetchall()
    return templates.TemplateResponse("event.html", {"request": request, "event": event, "rsvps": rsvps, "user_id": user_id})

@app.post("/admin/cancel/{event_id}")
async def cancel_event(request: Request, event_id: int):
    user_id = request.session.get("user_id")
    if not user_id or not request.session.get("is_admin"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET is_cancelled = 1 WHERE id = ?", (event_id,))
    conn.commit()
    return RedirectResponse(url="/admin/events")

@app.post("/calendar/rsvp/{event_id}")
async def rsvp_event(request: Request, event_id: int, status: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO rsvps (event_id, user_id, status) VALUES (?, ?, ?)", (event_id, user_id, status))
    conn.commit()
    return RedirectResponse(url=f"/calendar/{event_id}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)