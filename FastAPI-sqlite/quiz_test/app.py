from fastapi import FastAPI, Request, Form, HTTPException, Depends
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse
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

@app.get("/login/{member_id}")
async def login(request: Request, member_id: str):
    request.session["member_id"] = member_id
    request.session["is_admin"] = member_id == "admin"
    return render_template_string("<h1>Logged in as {{ member_id }}</h1>", member_id=member_id)

@app.post("/quizzes/create")
async def create_quiz(request: Request, title: str = Form(...), question: str = Form(...), correct_answer: str = Form(...)):
    if "member_id" not in request.session:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO quizzes (creator_id, title, question, correct_answer) VALUES (?, ?, ?, ?)", (request.session["member_id"], title, question, correct_answer))
    conn.commit()
    conn.close()
    return render_template_string("<h1>Quiz created</h1>")

@app.get("/quizzes")
async def list_quizzes(request: Request):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quizzes WHERE is_deleted = 0 ORDER BY created_at DESC")
    quizzes = cursor.fetchall()
    conn.close()
    return render_template_string("""
        <h1>Quizzes</h1>
        <ul>
            {% for quiz in quizzes %}
                <li><a href="/quizzes/{{ quiz.quiz_id }}">{{ quiz.title }}</a></li>
            {% endfor %}
        </ul>
    """, quizzes=quizzes)

@app.get("/quizzes/{quiz_id}")
async def take_quiz(request: Request, quiz_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quizzes WHERE quiz_id = ? AND is_deleted = 0", (quiz_id,))
    quiz = cursor.fetchone()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    conn.close()
    return render_template_string("""
        <h1>{{ quiz.title }}</h1>
        <form action="/quizzes/submit/{{ quiz_id }}" method="post">
            <p>{{ quiz.question }}</p>
            <input type="text" name="answer">
            <button type="submit">Submit</button>
        </form>
    """, quiz=quiz)

@app.post("/quizzes/submit/{quiz_id}")
async def submit_answer(request: Request, quiz_id: int, answer: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quizzes WHERE quiz_id = ? AND is_deleted = 0", (quiz_id,))
    quiz = cursor.fetchone()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    is_correct = answer == quiz["correct_answer"]
    cursor.execute("INSERT INTO attempts (quiz_id, user_id, submitted_answer, is_correct) VALUES (?, ?, ?, ?)", (quiz_id, request.session["member_id"], answer, is_correct))
    conn.commit()
    conn.close()
    return render_template_string("<h1>Answer submitted</h1>")

@app.get("/attempts")
async def view_attempts(request: Request):
    if "member_id" not in request.session:
        raise HTTPException(status_code=401, detail="Not logged in")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM attempts JOIN quizzes ON attempts.quiz_id = quizzes.quiz_id WHERE attempts.user_id = ? ORDER BY attempts.created_at DESC", (request.session["member_id"],))
    attempts = cursor.fetchall()
    conn.close()
    return render_template_string("""
        <h1>My Attempts</h1>
        <ul>
            {% for attempt in attempts %}
                <li>{{ attempt.title }} - {{ attempt.submitted_answer }} - {% if attempt.is_correct %}Correct{% else %}Incorrect{% endif %}</li>
            {% endfor %}
        </ul>
    """, attempts=attempts)

@app.post("/quizzes/delete/{quiz_id}")
async def delete_quiz(request: Request, quiz_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=401, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quizzes WHERE quiz_id = ?", (quiz_id,))
    quiz = cursor.fetchone()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    cursor.execute("UPDATE quizzes SET is_deleted = 1 WHERE quiz_id = ?", (quiz_id,))
    conn.commit()
    conn.close()
    return render_template_string("<h1>Quiz deleted</h1>")

@app.post("/admin/delete_quiz/{quiz_id}")
async def admin_delete_quiz(request: Request, quiz_id: int):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=401, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quizzes WHERE quiz_id = ?", (quiz_id,))
    quiz = cursor.fetchone()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    cursor.execute("UPDATE quizzes SET is_deleted = 1 WHERE quiz_id = ?", (quiz_id,))
    conn.commit()
    conn.close()
    return render_template_string("<h1>Quiz deleted</h1>")

@app.get("/admin/quizzes")
async def admin_list_quizzes(request: Request):
    if "member_id" not in request.session or not request.session["is_admin"]:
        raise HTTPException(status_code=401, detail="Not authorized")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quizzes WHERE is_deleted = 0 ORDER BY created_at DESC")
    quizzes = cursor.fetchall()
    conn.close()
    return render_template_string("""
        <h1>Admin Quizzes</h1>
        <ul>
            {% for quiz in quizzes %}
                <li><a href="/quizzes/{{ quiz.quiz_id }}">{{ quiz.title }}</a></li>
            {% endfor %}
        </ul>
    """, quizzes=quizzes)

def main():
    conn = sqlite3.connect("mock_db.sqlite3")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            question TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            submitted_answer TEXT NOT NULL,
            is_correct BOOLEAN NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES ('user', 'user@example.com', '<hashed>', 0, 0)")
    cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES ('admin', 'admin@example.com', '<hashed>', 1, 0)")
    cursor.execute("INSERT INTO quizzes (creator_id, title, question, correct_answer) VALUES (2, 'Welcome Quiz', 'What is 2 + 2?', '4')")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)