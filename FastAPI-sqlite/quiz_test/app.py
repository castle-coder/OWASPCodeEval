from fastapi import FastAPI, Depends, HTTPException, Form, Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, text
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from jinja2 import Template

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key_here")

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    email = Column(String, nullable=False)
    password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=0)
    is_deleted = Column(Boolean, default=0)
    quizzes_created = relationship('Quiz', back_populates='creator', primaryjoin='User.user_id == Quiz.creator_id')

class Quiz(Base):
    __tablename__ = 'quizzes'
    quiz_id = Column(Integer, primary_key=True, autoincrement=True)
    creator_id = Column(Integer, ForeignKey('users.user_id'))
    title = Column(String, nullable=False)
    question = Column(String, nullable=False)
    correct_answer = Column(String, nullable=False)
    is_deleted = Column(Boolean, default=0)
    created_at = Column(DateTime, default=datetime.now)
    creator = relationship('User', back_populates='quizzes_created')
    attempts = relationship('Attempt', back_populates='quiz')

class Attempt(Base):
    __tablename__ = 'attempts'
    attempt_id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(Integer, ForeignKey('quizzes.quiz_id'))
    user_id = Column(Integer, ForeignKey('users.user_id'))
    submitted_answer = Column(String, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    quiz = relationship('Quiz', back_populates='attempts')
    user = relationship('User', back_populates='attempts')

engine = create_engine('sqlite:///mock_db.sqlite3')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def render_template_string(html: str, **context):
    return HTMLResponse(Template(html).render(**context))

def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()

@app.get("/login/{member_id}")
async def login(request: Request, member_id: int):
    request.session['member_id'] = member_id
    request.session['is_admin'] = False
    return RedirectResponse("/")

@app.post("/quizzes/create")
async def create_quiz(request: Request, title: str = Form(...), question: str = Form(...), correct_answer: str = Form(...), db: Session = Depends(get_db)):
    if 'member_id' not in request.session:
        raise HTTPException(status_code=401, detail="Not logged in")
    new_quiz = Quiz(title=title, question=question, correct_answer=correct_answer, creator_id=request.session['member_id'])
    db.add(new_quiz)
    db.commit()
    return RedirectResponse("/quizzes")

@app.get("/quizzes")
async def list_quizzes(request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == request.session['member_id']).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")
    quizzes = db.query(Quiz).filter(Quiz.is_deleted == False).order_by(Quiz.created_at.desc()).all()
    return render_template_string('''
        <html>
        <body>
            <h1>Quizzes</h1>
            <ul>
                {% for quiz in quizzes %}
                    <li><a href="/quizzes/{{ quiz.quiz_id }}">{{ quiz.title }}</a></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', quizzes=quizzes)

@app.get("/quizzes/{quiz_id}")
async def take_quiz(request: Request, quiz_id: int, db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id, Quiz.is_deleted == False).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return render_template_string('''
        <html>
        <body>
            <h1>{{ quiz.title }}</h1>
            <p>{{ quiz.question }}</p>
            <form method="post" action="/quizzes/submit/{{ quiz.quiz_id }}">
                <input type="text" name="answer">
                <input type="submit" value="Submit">
            </form>
        </body>
        </html>
    ''', quiz=quiz)

@app.post("/quizzes/submit/{quiz_id}")
async def submit_answer(request: Request, quiz_id: int, answer: str = Form(...), db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id, Quiz.is_deleted == False).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    is_correct = answer == quiz.correct_answer
    new_attempt = Attempt(quiz_id=quiz_id, user_id=request.session['member_id'], submitted_answer=answer, is_correct=is_correct)
    db.add(new_attempt)
    db.commit()
    return render_template_string('''
        <html>
        <body>
            <h1>Result</h1>
            {% if is_correct %}
                <p>Correct!</p>
            {% else %}
                <p>Incorrect. The correct answer was {{ quiz.correct_answer }}</p>
            {% endif %}
        </body>
        </html>
    ''', is_correct=is_correct, quiz=quiz)

@app.get("/attempts")
async def view_attempts(request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == request.session['member_id']).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")
    attempts = db.query(Attempt).filter(Attempt.user_id == user.user_id).order_by(Attempt.created_at.desc()).all()
    return render_template_string('''
        <html>
        <body>
            <h1>Attempts</h1>
            <ul>
                {% for attempt in attempts %}
                    <li>{{ attempt.quiz.title }} - {{ attempt.submitted_answer }} - {% if attempt.is_correct %}Correct{% else %}Incorrect{% endif %}</li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', attempts=attempts)

@app.post("/quizzes/delete/{quiz_id}")
async def delete_quiz(request: Request, quiz_id: int, db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id, Quiz.is_deleted == False, Quiz.creator_id == request.session['member_id']).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    quiz.is_deleted = True
    db.commit()
    return RedirectResponse("/quizzes")

@app.post("/admin/delete_quiz/{quiz_id}")
async def admin_delete_quiz(request: Request, quiz_id: int, db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id, Quiz.is_deleted == False).first()
    if not quiz or not request.session.get('is_admin', False):
        raise HTTPException(status_code=404, detail="Quiz not found or not admin")
    quiz.is_deleted = True
    db.commit()
    return RedirectResponse("/admin/quizzes")

@app.get("/admin/quizzes")
async def admin_list_quizzes(request: Request, db: Session = Depends(get_db)):
    if not request.session.get('is_admin', False):
        raise HTTPException(status_code=401, detail="Not admin")
    quizzes = db.query(Quiz).filter(Quiz.is_deleted == False).order_by(Quiz.created_at.desc()).all()
    return render_template_string('''
        <html>
        <body>
            <h1>Admin Quizzes</h1>
            <ul>
                {% for quiz in quizzes %}
                    <li><a href="/quizzes/{{ quiz.quiz_id }}">{{ quiz.title }}</a> <form method="post" action="/admin/delete_quiz/{{ quiz.quiz_id }}"><input type="submit" value="Delete"></form></li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', quizzes=quizzes)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)