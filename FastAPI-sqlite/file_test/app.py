from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Form, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from starlette.requests import Request
from starlette.status import HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND
from datetime import datetime
import sqlite3
import os

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

DATABASE = "mock_db.sqlite3"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
def startup():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT,
            is_admin  BOOLEAN
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            filename     TEXT,
            description  TEXT,
            uploaded_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked   BOOLEAN DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id     INTEGER,
            user_id     INTEGER,
            reason      TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(file_id) REFERENCES files(id),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    conn.execute('''
        INSERT INTO users (username, is_admin) VALUES ('user', 0)
    ''')
    conn.execute('''
        INSERT INTO users (username, is_admin) VALUES ('admin', 1)
    ''')
    conn.commit()
    conn.close()

@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    request.session["user_id"] = user_id
    request.session["is_admin"] = user_id == 1
    return RedirectResponse("/files")

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), description: str = Form(None)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Not logged in")
    filename = file.filename
    file_path = os.path.join("uploads", filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    conn = get_db()
    conn.execute('''
        INSERT INTO files (user_id, filename, description) VALUES (?, ?, ?)
    ''', (user_id, filename, description))
    conn.commit()
    conn.close()
    return RedirectResponse("/files")

@app.get("/download/{file_id}")
async def download_file(request: Request, file_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Not logged in")
    conn = get_db()
    file = conn.execute('''
        SELECT * FROM files WHERE id = ? AND is_blocked = 0
    ''', (file_id,)).fetchone()
    conn.close()
    if not file:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="File not found")
    file_path = os.path.join("uploads", file["filename"])
    return FileResponse(file_path, filename=file["filename"])

@app.get("/files")
async def list_files(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Not logged in")
    conn = get_db()
    if user_id == 1:
        files = conn.execute('''
            SELECT * FROM files
        ''').fetchall()
    else:
        files = conn.execute('''
            SELECT * FROM files WHERE is_blocked = 0
        ''').fetchall()
    conn.close()
    return templates.TemplateResponse("files.html", {"request": request, "files": files})

@app.post("/delete/{file_id}")
async def delete_file(request: Request, file_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Not logged in")
    conn = get_db()
    file = conn.execute('''
        SELECT * FROM files WHERE id = ? AND user_id = ?
    ''', (file_id, user_id)).fetchone()
    if not file:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="File not found")
    file_path = os.path.join("uploads", file["filename"])
    os.remove(file_path)
    conn.execute('''
        DELETE FROM files WHERE id = ?
    ''', (file_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/files")

@app.post("/admin/block/{file_id}")
async def block_file(request: Request, file_id: int):
    user_id = request.session.get("user_id")
    if not user_id or not request.session.get("is_admin"):
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Not authorized")
    conn = get_db()
    conn.execute('''
        UPDATE files SET is_blocked = 1 WHERE id = ?
    ''', (file_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/files")

@app.post("/report/{file_id}")
async def report_file(request: Request, file_id: int, reason: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Not logged in")
    conn = get_db()
    conn.execute('''
        INSERT INTO reports (file_id, user_id, reason) VALUES (?, ?, ?)
    ''', (file_id, user_id, reason))
    conn.commit()
    conn.close()
    return RedirectResponse("/files")