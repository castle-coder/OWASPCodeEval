from flask import Flask, request, redirect, url_for, session, render_template_string
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATABASE = 'mock_db.sqlite3'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    quizzes = conn.execute('SELECT * FROM quizzes').fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <head>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
        </head>
        <body>
            <div class="container">
                <h1>Quizzes</h1>
                <a href="/login/1" class="btn btn-primary">Login</a>
                <a href="/quiz/create" class="btn btn-primary">Create Quiz</a>
                <ul>
                    {% for quiz in quizzes %}
                    <li>
                        <a href="/quiz/{{ quiz.id }}">{{ quiz.title }}</a>
                        <a href="/quiz/edit/{{ quiz.id }}" class="btn btn-warning">Edit</a>
                        <a href="/quiz/delete/{{ quiz.id }}" class="btn btn-danger">Delete</a>
                    </li>
                    {% endfor %}
                </ul>
                <a href="/quiz/leaderboard" class="btn btn-primary">Leaderboard</a>
            </div>
        </body>
        </html>
    ''', quizzes=quizzes)

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = False
    return redirect(url_for('index'))

@app.route('/quiz/create', methods=['GET', 'POST'])
def create_quiz():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        questions = request.form.getlist('question[]')
        options = request.form.getlist('options[]')
        correct_answers = request.form.getlist('correct_answer[]')
        conn = get_db_connection()
        quiz_id = conn.execute('INSERT INTO quizzes (user_id, title, description) VALUES (?, ?, ?)', (session['user_id'], title, description)).lastrowid
        for i in range(len(questions)):
            conn.execute('INSERT INTO questions (quiz_id, question, options, correct_answer) VALUES (?, ?, ?, ?)', (quiz_id, questions[i], options[i], correct_answers[i]))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template_string('''
        <html>
        <head>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
        </head>
        <body>
            <div class="container">
                <h1>Create Quiz</h1>
                <form method="post">
                    <div class="form-group">
                        <label for="title">Title</label>
                        <input type="text" class="form-control" id="title" name="title" required>
                    </div>
                    <div class="form-group">
                        <label for="description">Description</label>
                        <textarea class="form-control" id="description" name="description" required></textarea>
                    </div>
                    <div class="form-group">
                        <label for="question">Question</label>
                        <input type="text" class="form-control" id="question" name="question[]" required>
                    </div>
                    <div class="form-group">
                        <label for="options">Options</label>
                        <input type="text" class="form-control" id="options" name="options[]" required>
                    </div>
                    <div class="form-group">
                        <label for="correct_answer">Correct Answer</label>
                        <input type="text" class="form-control" id="correct_answer" name="correct_answer[]" required>
                    </div>
                    <button type="submit" class="btn btn-primary">Create Quiz</button>
                </form>
            </div>
        </body>
        </html>
    ''')

@app.route('/quiz/edit/<quiz_id>', methods=['GET', 'POST'])
def edit_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    conn = get_db_connection()
    quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    if quiz['user_id'] != session['user_id']:
        return redirect(url_for('index'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        questions = request.form.getlist('question[]')
        options = request.form.getlist('options[]')
        correct_answers = request.form.getlist('correct_answer[]')
        conn.execute('UPDATE quizzes SET title = ?, description = ? WHERE id = ?', (title, description, quiz_id))
        conn.execute('DELETE FROM questions WHERE quiz_id = ?', (quiz_id,))
        for i in range(len(questions)):
            conn.execute('INSERT INTO questions (quiz_id, question, options, correct_answer) VALUES (?, ?, ?, ?)', (quiz_id, questions[i], options[i], correct_answers[i]))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    questions = conn.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <head>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
        </head>
        <body>
            <div class="container">
                <h1>Edit Quiz</h1>
                <form method="post">
                    <div class="form-group">
                        <label for="title">Title</label>
                        <input type="text" class="form-control" id="title" name="title" value="{{ quiz.title }}" required>
                    </div>
                    <div class="form-group">
                        <label for="description">Description</label>
                        <textarea class="form-control" id="description" name="description" required>{{ quiz.description }}</textarea>
                    </div>
                    {% for question in questions %}
                    <div class="form-group">
                        <label for="question">Question</label>
                        <input type="text" class="form-control" id="question" name="question[]" value="{{ question.question }}" required>
                    </div>
                    <div class="form-group">
                        <label for="options">Options</label>
                        <input type="text" class="form-control" id="options" name="options[]" value="{{ question.options }}" required>
                    </div>
                    <div class="form-group">
                        <label for="correct_answer">Correct Answer</label>
                        <input type="text" class="form-control" id="correct_answer" name="correct_answer[]" value="{{ question.correct_answer }}" required>
                    </div>
                    {% endfor %}
                    <button type="submit" class="btn btn-primary">Edit Quiz</button>
                </form>
            </div>
        </body>
        </html>
    ''', quiz=quiz, questions=questions)

@app.route('/quiz/delete/<quiz_id>', methods=['POST'])
def delete_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    conn = get_db_connection()
    quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    if quiz['user_id'] != session['user_id']:
        return redirect(url_for('index'))
    conn.execute('DELETE FROM questions WHERE quiz_id = ?', (quiz_id,))
    conn.execute('DELETE FROM quizzes WHERE id = ?', (quiz_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/quiz/<quiz_id>', methods=['GET', 'POST'])
def take_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    conn = get_db_connection()
    quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    questions = conn.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
    if request.method == 'POST':
        answers = request.form.getlist('answer[]')
        score = 0
        for i in range(len(questions)):
            if questions[i]['correct_answer'] == answers[i]:
                score += 1
        conn.execute('INSERT INTO results (user_id, quiz_id, score) VALUES (?, ?, ?)', (session['user_id'], quiz_id, score))
        conn.commit()
        conn.close()
        return redirect(url_for('results', quiz_id=quiz_id))
    conn.close()
    return render_template_string('''
        <html>
        <head>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
        </head>
        <body>
            <div class="container">
                <h1>Take Quiz</h1>
                <form method="post">
                    {% for question in questions %}
                    <div class="form-group">
                        <label for="question">{{ question.question }}</label>
                        <select class="form-control" id="answer" name="answer[]">
                            {% for option in question.options.split(',') %}
                            <option value="{{ option }}">{{ option }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    {% endfor %}
                    <button type="submit" class="btn btn-primary">Submit</button>
                </form>
            </div>
        </body>
        </html>
    ''', quiz=quiz, questions=questions)

@app.route('/quiz/results/<quiz_id>')
def results(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    conn = get_db_connection()
    quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    questions = conn.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
    result = conn.execute('SELECT * FROM results WHERE user_id = ? AND quiz_id = ?', (session['user_id'], quiz_id)).fetchone()
    conn.close()
    
    if not result:
        return render_template_string('''
            <html>
            <head>
                <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
            </head>
            <body>
                <div class="container">
                    <h1>Quiz Results</h1>
                    <h2>{{ quiz.title }}</h2>
                    <p>You haven't taken this quiz yet.</p>
                    <a href="/quiz/{{ quiz.id }}" class="btn btn-primary">Take Quiz</a>
                    <a href="/" class="btn btn-secondary">Back to Quizzes</a>
                </div>
            </body>
            </html>
        ''', quiz=quiz)
    
    return render_template_string('''
        <html>
        <head>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
        </head>
        <body>
            <div class="container">
                <h1>Quiz Results</h1>
                <h2>{{ quiz.title }}</h2>
                <p>Your score: {{ result.score }}/{{ questions|length }}</p>
                <p>Completed at: {{ result.completed_at }}</p>
                <a href="/" class="btn btn-primary">Back to Quizzes</a>
            </div>
        </body>
        </html>
    ''', quiz=quiz, questions=questions, result=result)

@app.route('/quiz/leaderboard')
def leaderboard():
    conn = get_db_connection()
    results = conn.execute('SELECT * FROM results ORDER BY score DESC').fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <head>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
        </head>
        <body>
            <div class="container">
                <h1>Leaderboard</h1>
                <table class="table">
                    <thead>
                        <tr>
                            <th>User</th>
                            <th>Quiz</th>
                            <th>Score</th>
                            <th>Time Taken</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for result in results %}
                        <tr>
                            <td>{{ result.user_id }}</td>
                            <td>{{ result.quiz_id }}</td>
                            <td>{{ result.score }}</td>
                            <td>{{ result.completed_at - result.created_at }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                <a href="/" class="btn btn-primary">Back to Quizzes</a>
            </div>
        </body>
        </html>
    ''', results=results)

if __name__ == '__main__':
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, is_admin BOOLEAN NOT NULL DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS quizzes (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(user_id))')
    conn.execute('CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY AUTOINCREMENT, quiz_id INTEGER NOT NULL, question TEXT NOT NULL, options TEXT NOT NULL, correct_answer TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (quiz_id) REFERENCES quizzes(id))')
    conn.execute('CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, quiz_id INTEGER NOT NULL, score INTEGER NOT NULL, completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(user_id), FOREIGN KEY (quiz_id) REFERENCES quizzes(id))')
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    conn.execute("INSERT INTO quizzes (user_id, title, description) VALUES (?, ?, ?)", (1, 'Math Quiz', 'Basic mathematics questions'))
    conn.execute("INSERT INTO quizzes (user_id, title, description) VALUES (?, ?, ?)", (2, 'Science Quiz', 'General science questions'))
    conn.execute("INSERT INTO questions (quiz_id, question, options, correct_answer) VALUES (?, ?, ?, ?)", (1, 'What is 2+2?', '["3","4","5","6"]', '4'))
    conn.execute("INSERT INTO questions (quiz_id, question, options, correct_answer) VALUES (?, ?, ?, ?)", (1, 'What is 3*3?', '["6","7","8","9"]', '9'))
    conn.commit()
    conn.close()
    app.run(debug=True)