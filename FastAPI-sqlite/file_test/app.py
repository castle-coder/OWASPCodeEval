from fastapi import FastAPI, Request, Form, HTTPException, Depends, File, UploadFile, status
from fastapi.responses import HTMLResponse, StreamingResponse
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
def startup_event():
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
        INSERT INTO files (owner_id, original_name, size, mime_type, data, is_deleted)
        SELECT 2, 'sample.txt', 11, 'text/plain', X'73616d706c652074657874', 0
        WHERE NOT EXISTS (SELECT 1 FROM files WHERE original_name = 'sample.txt')
    ''')
    conn.commit()
    conn.close()

@app.get("/login/{member_id}")
async def login(request: Request, member_id: str):
    request.session["member_id"] = member_id
    request.session["is_admin"] = member_id == "admin"
    return render_template_string('<html><body><h1>Logged in as {{ member_id }}</h1></body></html>', member_id=member_id)

@app.get("/files/upload")
async def upload_form(request: Request):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in first</h1></body></html>')
    return render_template_string('''
        <html>
        <body>
            <h1>Upload a file</h1>
            <form action="/files/upload" method="post" enctype="multipart/form-data">
                <input type="file" name="file">
                <input type="submit" value="Upload">
            </form>
        </body>
        </html>
    ''')

@app.post("/files/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in first</h1></body></html>')
    file_data = await file.read()
    conn = get_db()
    conn.execute('''
        INSERT INTO files (owner_id, original_name, size, mime_type, data, is_deleted)
        VALUES (?, ?, ?, ?, ?, 0)
    ''', (request.session["member_id"], file.filename, len(file_data), file.content_type, file_data))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>File uploaded successfully</h1></body></html>')

@app.get("/files")
async def list_files(request: Request):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in first</h1></body></html>')
    conn = get_db()
    files = conn.execute('''
        SELECT file_id, original_name, size, created_at
        FROM files
        WHERE owner_id = ? AND is_deleted = 0
        ORDER BY created_at DESC
    ''', (request.session["member_id"],)).fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>My Files</h1>
            <ul>
                {% for file in files %}
                <li><a href="/files/{{ file.file_id }}/download">{{ file.original_name }} ({{ file.size }} bytes, {{ file.created_at }})</a></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', files=files)

@app.get("/files/{file_id}/download")
async def download_file(request: Request, file_id: int):
    conn = get_db()
    file = conn.execute('''
        SELECT file_id, original_name, mime_type, data
        FROM files
        WHERE file_id = ? AND is_deleted = 0
    ''', (file_id,)).fetchone()
    conn.close()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    if request.session["member_id"] != str(file["owner_id"]) and not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return StreamingResponse(file["data"], media_type=file["mime_type"], headers={"Content-Disposition": f"attachment; filename={file['original_name']}"})

@app.post("/files/delete/{file_id}")
async def delete_file(request: Request, file_id: int):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in first</h1></body></html>')
    conn = get_db()
    file = conn.execute('''
        SELECT file_id, owner_id
        FROM files
        WHERE file_id = ? AND is_deleted = 0
    ''', (file_id,)).fetchone()
    conn.close()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    if request.session["member_id"] != str(file["owner_id"]) and not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return render_template_string('''
        <html>
        <body>
            <h1>Confirm deletion</h1>
            <form action="/files/delete/{{ file_id }}" method="post">
                <input type="submit" value="Delete">
            </form>
        </body>
        </html>
    ''', file_id=file_id)

@app.post("/files/delete/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file_confirm(request: Request, file_id: int):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in first</h1></body></html>')
    conn = get_db()
    conn.execute('''
        UPDATE files
        SET is_deleted = 1
        WHERE file_id = ?
    ''', (file_id,))
    conn.commit()
    conn.close()

@app.get("/admin/files")
async def admin_list_files(request: Request):
    if "member_id" not in request.session or not request.session.get("is_admin"):
        return render_template_string('<html><body><h1>Access denied</h1></body></html>')
    conn = get_db()
    files = conn.execute('''
        SELECT file_id, owner_id, original_name, size, created_at
        FROM files
        WHERE is_deleted = 0
    ''').fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>Admin Files</h1>
            <ul>
                {% for file in files %}
                <li><a href="/files/{{ file.file_id }}/download">{{ file.original_name }} ({{ file.size }} bytes, {{ file.created_at }})</a></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', files=files)

@app.post("/admin/delete_file/{file_id}")
async def admin_delete_file(request: Request, file_id: int):
    if "member_id" not in request.session or not request.session.get("is_admin"):
        return render_template_string('<html><body><h1>Access denied</h1></body></html>')
    return render_template_string('''
        <html>
        <body>
            <h1>Confirm deletion</h1>
            <form action="/admin/delete_file/{{ file_id }}" method="post">
                <input type="submit" value="Delete">
            </form>
        </body>
        </html>
    ''', file_id=file_id)

@app.post("/admin/delete_file/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_file_confirm(request: Request, file_id: int):
    if "member_id" not in request.session or not request.session.get("is_admin"):
        return render_template_string('<html><body><h1>Access denied</h1></body></html>')
    conn = get_db()
    conn.execute('''
        UPDATE files
        SET is_deleted = 1
        WHERE file_id = ?
    ''', (file_id,))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)