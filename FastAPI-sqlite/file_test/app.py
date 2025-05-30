from fastapi import FastAPI, Request, Form, HTTPException, Depends, File, UploadFile, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
import uvicorn
from datetime import datetime

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key_here")

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

def get_db():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0
        )
    ''')
    cursor.execute('''
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
    cursor.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'user', 'user@example.com', 'hashed_password', 0, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'user')
    ''')
    cursor.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        SELECT 'admin', 'admin@example.com', 'hashed_password', 1, 0
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
    ''')
    cursor.execute('''
        INSERT INTO files (owner_id, original_name, size, mime_type, data, is_deleted)
        SELECT 2, 'sample.txt', 11, 'text/plain', X'73616d706c652074657874', 0
        WHERE NOT EXISTS (SELECT 1 FROM files WHERE original_name = 'sample.txt')
    ''')
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/login/{member_id}")
async def login(member_id: str, request: Request):
    request.session["member_id"] = member_id
    request.session["is_admin"] = member_id == "admin"
    return render_template_string('<html><body><h1>Logged in as {{ member_id }}</h1></body></html>', member_id=member_id)

@app.get("/files/upload")
async def upload_form(request: Request):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in to upload a file.</h1></body></html>')
    return render_template_string('''
        <html>
            <body>
                <h1>Upload a File</h1>
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
        return render_template_string('<html><body><h1>Please log in to upload a file.</h1></body></html>')
    file_data = await file.read()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO files (owner_id, original_name, size, mime_type, data, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (request.session["member_id"], file.filename, len(file_data), file.content_type, file_data, 0))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>File uploaded successfully.</h1></body></html>')

@app.get("/files")
async def list_files(request: Request):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in to view your files.</h1></body></html>')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT file_id, original_name, size, created_at
        FROM files
        WHERE owner_id = ? AND is_deleted = 0
        ORDER BY created_at DESC
    ''', (request.session["member_id"],))
    files = cursor.fetchall()
    conn.close()
    return render_template_string('''
        <html>
            <body>
                <h1>My Files</h1>
                <ul>
                    {% for file in files %}
                        <li>
                            <a href="/files/{{ file.file_id }}/download">{{ file.original_name }} ({{ file.size }} bytes)</a>
                            <form action="/files/delete/{{ file.file_id }}" method="post" style="display:inline;">
                                <input type="submit" value="Delete">
                            </form>
                        </li>
                    {% endfor %}
                </ul>
            </body>
        </html>
    ''', files=files)

@app.get("/files/{file_id}/download")
async def download_file(request: Request, file_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT mime_type, data
        FROM files
        WHERE file_id = ? AND is_deleted = 0
    ''', (file_id,))
    file = cursor.fetchone()
    conn.close()
    if file:
        return StreamingResponse(file[1], media_type=file[0], headers={"Content-Disposition": f"attachment; filename={file[2]}"})
    else:
        raise HTTPException(status_code=404, detail="File not found")

@app.post("/files/delete/{file_id}")
async def delete_file(request: Request, file_id: int):
    if "member_id" not in request.session:
        return render_template_string('<html><body><h1>Please log in to delete a file.</h1></body></html>')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT owner_id
        FROM files
        WHERE file_id = ?
    ''', (file_id,))
    owner_id = cursor.fetchone()
    if owner_id and (owner_id[0] == request.session["member_id"] or request.session["is_admin"]):
        cursor.execute('''
            UPDATE files
            SET is_deleted = 1
            WHERE file_id = ?
        ''', (file_id,))
        conn.commit()
        conn.close()
        return render_template_string('<html><body><h1>File deleted successfully.</h1></body></html>')
    else:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this file")

@app.get("/admin/files")
async def admin_list_files(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return render_template_string('<html><body><h1>Please log in as an admin to view all files.</h1></body></html>')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT file_id, owner_id, original_name, size, created_at
        FROM files
        WHERE is_deleted = 0
    ''')
    files = cursor.fetchall()
    conn.close()
    return render_template_string('''
        <html>
            <body>
                <h1>All Files</h1>
                <ul>
                    {% for file in files %}
                        <li>
                            <a href="/files/{{ file.file_id }}/download">{{ file.original_name }} ({{ file.size }} bytes)</a>
                            <form action="/admin/delete_file/{{ file.file_id }}" method="post" style="display:inline;">
                                <input type="submit" value="Delete">
                            </form>
                        </li>
                    {% endfor %}
                </ul>
            </body>
        </html>
    ''', files=files)

@app.post("/admin/delete_file/{file_id}")
async def admin_delete_file(request: Request, file_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        return render_template_string('<html><body><h1>Please log in as an admin to delete a file.</h1></body></html>')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE files
        SET is_deleted = 1
        WHERE file_id = ?
    ''', (file_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>File deleted successfully.</h1></body></html>')

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)