from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Form, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from starlette.requests import Request
from starlette.exceptions import HTTPException as StarletteHTTPException
import sqlite3
import os
from datetime import datetime

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
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    conn.commit()
    conn.close()

def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    is_admin = request.session.get("is_admin")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user_id": user_id, "is_admin": is_admin}

@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    request.session["user_id"] = user_id
    request.session["is_admin"] = user_id == 1
    return RedirectResponse("/files")

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), description: str = Form(None)):
    user = get_current_user(request)
    filename = file.filename
    file_path = os.path.join("uploads", filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    conn = get_db()
    conn.execute("INSERT INTO files (user_id, filename, description) VALUES (?, ?, ?)", (user["user_id"], filename, description))
    conn.commit()
    conn.close()
    return RedirectResponse("/files")

@app.get("/download/{file_id}")
async def download_file(request: Request, file_id: int):
    user = get_current_user(request)
    conn = get_db()
    file = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    if file["is_blocked"] and not user["is_admin"]:
        raise HTTPException(status_code=403, detail="File is blocked")
    file_path = os.path.join("uploads", file["filename"])
    return FileResponse(file_path, filename=file["filename"])

@app.get("/files")
async def list_files(request: Request):
    user = get_current_user(request)
    conn = get_db()
    files = conn.execute("SELECT * FROM files WHERE is_blocked = 0").fetchall()
    if not user["is_admin"]:
        files = [file for file in files if file["user_id"] == user["user_id"]]
    return templates.TemplateResponse("files.html", {"request": request, "files": files})

@app.post("/delete/{file_id}")
async def delete_file(request: Request, file_id: int):
    user = get_current_user(request)
    conn = get_db()
    file = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    if file["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this file")
    file_path = os.path.join("uploads", file["filename"])
    os.remove(file_path)
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/files")

@app.post("/admin/block/{file_id}")
async def block_file(request: Request, file_id: int):
    user = get_current_user(request)
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to block files")
    conn = get_db()
    conn.execute("UPDATE files SET is_blocked = 1 WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/files")

@app.post("/report/{file_id}")
async def report_file(request: Request, file_id: int, reason: str = Form(...)):
    user = get_current_user(request)
    conn = get_db()
    conn.execute("INSERT INTO reports (file_id, user_id, reason) VALUES (?, ?, ?)", (file_id, user["user_id"], reason))
    conn.commit()
    conn.close()
    return RedirectResponse("/files")