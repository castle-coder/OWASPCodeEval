from fastapi import FastAPI, Request, Form, HTTPException, Depends, File, UploadFile, status
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from jinja2 import Template
import sqlite3
from datetime import datetime

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

def get_db_connection():
    conn = sqlite3.connect("mock_db.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
async def startup_event():
    conn = get_db_connection()
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
        CREATE TABLE IF NOT EXISTS files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            size INTEGER NOT NULL,
            mime_type TEXT NOT NULL,
            data BLOB NOT NULL,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)", ('user', 'user@example.com', 'hashed_password', 0, 0))
    conn.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)", ('admin', 'admin@example.com', 'hashed_password', 1, 0))
    conn.execute("INSERT INTO files (owner_id, original_name, size, mime_type, data, is_deleted) VALUES (?, ?, ?, ?, ?, ?)", (2, 'sample.txt', 11, 'text/plain', b'sample text', 0))
    conn.commit()
    conn.close()

@app.get("/login/{member_id}")
async def login(request: Request, member_id: str):
    request.session["member_id"] = member_id
    request.session["is_admin"] = member_id == "admin"
    return render_template_string('<html><body><h1>Logged in as {{ member_id }}</h1></body></html>', member_id=member_id)

@app.get("/files/upload")
async def upload_file_form(request: Request):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Not logged in</h1></body></html>')
    return render_template_string('<html><body><form method="post" enctype="multipart/form-data"><input type="file" name="file"><input type="submit" value="Upload"></form></body></html>')

@app.post("/files/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Not logged in</h1></body></html>')
    file_data = await file.read()
    conn = get_db_connection()
    conn.execute("INSERT INTO files (owner_id, original_name, size, mime_type, data) VALUES (?, ?, ?, ?, ?)", (request.session["member_id"], file.filename, len(file_data), file.content_type, file_data))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>File uploaded successfully</h1></body></html>')

@app.get("/files")
async def list_files(request: Request):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Not logged in</h1></body></html>')
    conn = get_db_connection()
    files = conn.execute("SELECT file_id, original_name, size, created_at FROM files WHERE owner_id = ? AND is_deleted = 0 ORDER BY created_at DESC", (request.session["member_id"],)).fetchall()
    conn.close()
    return render_template_string('<html><body><h1>My Files</h1><ul>{% for file in files %}<li><a href="/files/{{ file.file_id }}/download">{{ file.original_name }} ({{ file.size }} bytes, {{ file.created_at }})</a> <form style="display:inline" action="/files/delete/{{ file.file_id }}" method="post"><input type="submit" value="Delete"></form></li>{% endfor %}</ul></body></html>', files=files)

@app.get("/files/<file_id>/download")
async def download_file(request: Request, file_id: int):
    conn = get_db_connection()
    file = conn.execute("SELECT data, mime_type FROM files WHERE file_id = ? AND is_deleted = 0", (file_id,)).fetchone()
    conn.close()
    if file:
        return StreamingResponse(io.BytesIO(file[0]), media_type=file[1], headers={"Content-Disposition": f"attachment; filename={file_id}.download"})
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/files/delete/<file_id>")
async def delete_file(request: Request, file_id: int):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Not logged in</h1></body></html>')
    conn = get_db_connection()
    if request.session["member_id"] == str(file_id) or request.session["is_admin"]:
        conn.execute("UPDATE files SET is_deleted = 1 WHERE file_id = ?", (file_id,))
        conn.commit()
        conn.close()
        return render_template_string('<html><body><h1>File deleted successfully</h1></body></html>')
    raise HTTPException(status_code=403, detail="You are not authorized to delete this file")

@app.get("/admin/files")
async def admin_list_files(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return render_template_string('<html><body><h1>Not logged in or not an admin</h1></body></html>')
    conn = get_db_connection()
    files = conn.execute("SELECT file_id, owner_id, original_name, size, created_at FROM files WHERE is_deleted = 0").fetchall()
    conn.close()
    return render_template_string('<html><body><h1>Admin Files</h1><ul>{% for file in files %}<li><a href="/files/{{ file.file_id }}/download">{{ file.original_name }} ({{ file.size }} bytes, {{ file.created_at }})</a> <form style="display:inline" action="/admin/delete_file/{{ file.file_id }}" method="post"><input type="submit" value="Delete"></form></li>{% endfor %}</ul></body></html>', files=files)

@app.post("/admin/delete_file/<file_id>")
async def admin_delete_file(request: Request, file_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return render_template_string('<html><body><h1>Not logged in or not an admin</h1></body></html>')
    conn = get_db_connection()
    conn.execute("UPDATE files SET is_deleted = 1 WHERE file_id = ?", (file_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>File deleted successfully</h1></body></html>')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)