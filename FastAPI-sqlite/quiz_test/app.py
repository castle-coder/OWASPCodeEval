from fastapi import FastAPI, Request, Form, HTTPException, Depends
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

def get_current_user(request: Request):
    member_id = request.session.get("member_id")
    if member_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return member_id

@app.on_event("startup")
def main():
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
    conn.execute('''
        INSERT INTO users (username, email, password, is_admin, is_deleted)
        VALUES ('user', 'user@example.com', '<hashed>', 0, 0),
               ('admin', 'admin@example.com', '<hashed>', 1, 0)
    ''')
    conn.execute('''
        INSERT INTO quizzes (creator_id, title, question, correct_answer, is_deleted)
        VALUES (2, 'Welcome Quiz', 'What is 2 + 2?', '4', 0)
    ''')
    conn.commit()
    conn.close()

@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    request.session["member_id"] = member_id
    request.session["is_admin"] = member_id == 2
    return render_template_string('<html><body><h1>Logged in as member {{ member_id }}</h1></body></html>', member_id=member_id)

@app.post("/quizzes/create")
async def create_quiz(request: Request, title: str = Form(...), question: str = Form(...), correct_answer: str = Form(...)):
    member_id = get_current_user(request)
    conn = get_db()
    conn.execute('INSERT INTO quizzes (creator_id, title, question, correct_answer, is_deleted) VALUES (?, ?, ?, ?, 0)', (member_id, title, question, correct_answer))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Quiz created successfully</h1></body></html>')

@app.get("/quizzes")
async def list_quizzes(request: Request):
    member_id = get_current_user(request)
    conn = get_db()
    quizzes = conn.execute('SELECT * FROM quizzes WHERE is_deleted = 0 ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>Available Quizzes</h1>
            <ul>
                {% for quiz in quizzes %}
                <li><a href="/quizzes/{{ quiz.quiz_id }}">{{ quiz.title }}</a></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', quizzes=quizzes)

@app.get("/quizzes/{quiz_id}")
async def take_quiz(request: Request, quiz_id: int):
    member_id = get_current_user(request)
    conn = get_db()
    quiz = conn.execute('SELECT * FROM quizzes WHERE quiz_id = ? AND is_deleted = 0', (quiz_id,)).fetchone()
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>{{ quiz.title }}</h1>
            <p>{{ quiz.question }}</p>
            <form action="/quizzes/submit/{{ quiz_id }}" method="post">
                <input type="text" name="submitted_answer" required>
                <button type="submit">Submit</button>
            </form>
        </body>
        </html>
    ''', quiz=quiz)

@app.post("/quizzes/submit/{quiz_id}")
async def submit_answer(request: Request, quiz_id: int, submitted_answer: str = Form(...)):
    member_id = get_current_user(request)
    conn = get_db()
    quiz = conn.execute('SELECT * FROM quizzes WHERE quiz_id = ? AND is_deleted = 0', (quiz_id,)).fetchone()
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    is_correct = submitted_answer == quiz['correct_answer']
    conn.execute('INSERT INTO attempts (quiz_id, user_id, submitted_answer, is_correct) VALUES (?, ?, ?, ?)', (quiz_id, member_id, submitted_answer, is_correct))
    conn.commit()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>Answer Submitted</h1>
            <p>Your answer is {{ "correct" if is_correct else "incorrect" }}</p>
        </body>
        </html>
    ''', is_correct=is_correct)

@app.get("/attempts")
async def view_attempts(request: Request):
    member_id = get_current_user(request)
    conn = get_db()
    attempts = conn.execute('SELECT * FROM attempts WHERE user_id = ? ORDER BY created_at DESC', (member_id,)).fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>My Attempts</h1>
            <ul>
                {% for attempt in attempts %}
                <li>
                    <h2>{{ attempt['quiz_id'] }}</h2>
                    <p>Submitted Answer: {{ attempt['submitted_answer'] }}</p>
                    <p>Correct: {{ "Yes" if attempt['is_correct'] else "No" }}</p>
                </li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', attempts=attempts)

@app.post("/quizzes/delete/{quiz_id}")
async def delete_quiz(request: Request, quiz_id: int):
    member_id = get_current_user(request)
    conn = get_db()
    quiz = conn.execute('SELECT * FROM quizzes WHERE quiz_id = ? AND creator_id = ?', (quiz_id, member_id)).fetchone()
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    conn.execute('UPDATE quizzes SET is_deleted = 1 WHERE quiz_id = ?', (quiz_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Quiz deleted successfully</h1></body></html>')

@app.post("/admin/delete_quiz/{quiz_id}")
async def admin_delete_quiz(request: Request, quiz_id: int):
    member_id = get_current_user(request)
    if not member_id == 2:
        raise HTTPException(status_code=403, detail="Admin access required")
    conn = get_db()
    quiz = conn.execute('SELECT * FROM quizzes WHERE quiz_id = ?', (quiz_id,)).fetchone()
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    conn.execute('UPDATE quizzes SET is_deleted = 1 WHERE quiz_id = ?', (quiz_id,))
    conn.commit()
    conn.close()
    return render_template_string('<html><body><h1>Quiz deleted successfully</h1></body></html>')

@app.get("/admin/quizzes")
async def admin_list_quizzes(request: Request):
    member_id = get_current_user(request)
    if not member_id == 2:
        raise HTTPException(status_code=403, detail="Admin access required")
    conn = get_db()
    quizzes = conn.execute('SELECT * FROM quizzes WHERE is_deleted = 0').fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>Active Quizzes</h1>
            <ul>
                {% for quiz in quizzes %}
                <li><a href="/quizzes/{{ quiz.quiz_id }}">{{ quiz.title }}</a></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', quizzes=quizzes)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)