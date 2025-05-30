from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Template
import sqlite3
from datetime import datetime

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

def get_db():
    conn = sqlite3.connect("mock_db.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/login/{member_id}")
async def login(request: Request, member_id: str):
    request.session["member_id"] = member_id
    request.session["is_admin"] = member_id == "admin"
    return render_template_string('<html><body><h1>Logged in as {{ member_id }}</h1></body></html>', member_id=member_id)

@app.post("/quizzes/create")
async def create_quiz(request: Request, title: str = Form(...), question: str = Form(...), correct_answer: str = Form(...)):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    conn.execute("INSERT INTO quizzes (creator_id, title, question, correct_answer) VALUES (?, ?, ?, ?)", (request.session["member_id"], title, question, correct_answer))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Quiz created successfully</h1></body></html>')

@app.get("/quizzes")
async def list_quizzes(request: Request):
    conn = get_db()
    quizzes = conn.execute("SELECT * FROM quizzes WHERE is_deleted = 0 ORDER BY created_at DESC").fetchall()
    conn.close()
    html = '<html><body><h1>Available Quizzes</h1><ul>'
    for quiz in quizzes:
        html += f'<li><a href="/quizzes/{quiz["quiz_id"]}">{quiz["title"]}</a></li>'
    html += '</ul></body></html>'
    return HTMLResponse(html)

@app.get("/quizzes/{quiz_id}")
async def take_quiz(request: Request, quiz_id: int):
    conn = get_db()
    quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id = ? AND is_deleted = 0", (quiz_id,)).fetchone()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    conn.close()
    return render_template_string('<html><body><h1>{{ quiz["title"] }}</h1><p>{{ quiz["question"] }}</p><form action="/quizzes/submit/{{ quiz["quiz_id"] }}" method="post"><input type="text" name="answer"><input type="submit" value="Submit"></form></body></html>', quiz=quiz)

@app.post("/quizzes/submit/{quiz_id}")
async def submit_answer(request: Request, quiz_id: int, answer: str = Form(...)):
    conn = get_db()
    quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id = ? AND is_deleted = 0", (quiz_id,)).fetchone()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    is_correct = answer == quiz["correct_answer"]
    conn.execute("INSERT INTO attempts (quiz_id, user_id, submitted_answer, is_correct) VALUES (?, ?, ?, ?)", (quiz_id, request.session["member_id"], answer, is_correct))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Answer submitted</h1><p>Your answer is {{ "correct" if is_correct else "incorrect" }}</p></body></html>', is_correct=is_correct)

@app.get("/attempts")
async def view_attempts(request: Request):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    attempts = conn.execute("SELECT q.title, a.submitted_answer, a.is_correct FROM attempts a JOIN quizzes q ON a.quiz_id = q.quiz_id WHERE a.user_id = ? ORDER BY a.created_at DESC", (request.session["member_id"],)).fetchall()
    conn.close()
    html = '<html><body><h1>Your Attempts</h1><ul>'
    for attempt in attempts:
        html += f'<li>{{ attempt["title"] }} - {{ attempt["submitted_answer"] }} - {{ "Correct" if attempt["is_correct"] else "Incorrect" }}</li>'
    html += '</ul></body></html>'
    return HTMLResponse(html)

@app.post("/quizzes/delete/{quiz_id}")
async def delete_quiz(request: Request, quiz_id: int):
    if "member_id" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    conn = get_db()
    quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id = ? AND creator_id = ?", (quiz_id, request.session["member_id"])).fetchone()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    conn.execute("UPDATE quizzes SET is_deleted = 1 WHERE quiz_id = ?", (quiz_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Quiz deleted successfully</h1></body></html>')

@app.post("/admin/delete_quiz/{quiz_id}")
async def admin_delete_quiz(request: Request, quiz_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    conn = get_db()
    quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id = ?", (quiz_id,)).fetchone()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    conn.execute("UPDATE quizzes SET is_deleted = 1 WHERE quiz_id = ?", (quiz_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Quiz deleted successfully</h1></body></html>')

@app.get("/admin/quizzes")
async def list_admin_quizzes(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    conn = get_db()
    quizzes = conn.execute("SELECT * FROM quizzes WHERE is_deleted = 0 ORDER BY created_at DESC").fetchall()
    conn.close()
    html = '<html><body><h1>Available Quizzes</h1><ul>'
    for quiz in quizzes:
        html += f'<li><a href="/quizzes/{quiz["quiz_id"]}">{quiz["title"]}</a></li>'
    html += '</ul></body></html>'
    return HTMLResponse(html)

def main():
    conn = sqlite3.connect("mock_db.sqlite3")
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
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            question TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS attempts (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            submitted_answer TEXT NOT NULL,
            is_correct BOOLEAN NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES ('user', 'user@example.com', '<hashed>', 0, 0)")
    conn.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES ('admin', 'admin@example.com', '<hashed>', 1, 0)")
    conn.execute("INSERT INTO quizzes (creator_id, title, question, correct_answer) VALUES (2, 'Welcome Quiz', 'What is 2 + 2?', '4')")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    import uvicorn
    main()
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)