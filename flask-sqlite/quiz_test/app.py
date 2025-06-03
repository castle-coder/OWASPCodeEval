from flask import Flask, request, session, render_template_string, redirect, url_for, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DB_FILE = 'mock_db.sqlite3'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = False
    return redirect(url_for('index'))

@app.route('/quiz', methods=['POST'])
def create_quiz():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    title = request.form['title']
    description = request.form['description']
    questions = request.form.getlist('question[]')
    options = request.form.getlist('options[]')
    correct_answers = request.form.getlist('correct_answer[]')

    conn = get_db_connection()
    quiz_id = conn.execute('INSERT INTO quizzes (user_id, title, description) VALUES (?, ?, ?)', (user_id, title, description)).lastrowid
    for question, option, correct_answer in zip(questions, options, correct_answers):
        conn.execute('INSERT INTO questions (quiz_id, question, options, correct_answer) VALUES (?, ?, ?, ?)', (quiz_id, question, option, correct_answer))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/quiz/edit/<quiz_id>', methods=['GET', 'POST'])
def edit_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        questions = request.form.getlist('question[]')
        options = request.form.getlist('options[]')
        correct_answers = request.form.getlist('correct_answer[]')

        conn = get_db_connection()
        conn.execute('UPDATE quizzes SET title = ?, description = ? WHERE id = ?', (title, description, quiz_id))
        conn.execute('DELETE FROM questions WHERE quiz_id = ?', (quiz_id,))
        for question, option, correct_answer in zip(questions, options, correct_answers):
            conn.execute('INSERT INTO questions (quiz_id, question, options, correct_answer) VALUES (?, ?, ?, ?)', (quiz_id, question, option, correct_answer))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    else:
        conn = get_db_connection()
        quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
        questions = conn.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
        conn.close()
        edit_form = render_template_string('''
            <form method="post">
                <input type="text" name="title" value="{{ quiz.title }}">
                <input type="text" name="description" value="{{ quiz.description }}">
                {% for question, option, correct_answer in zip(questions, questions|map(attribute='options'), questions|map(attribute='correct_answer')) %}
                    <input type="text" name="question[]" value="{{ question.question }}">
                    <input type="text" name="options[]" value="{{ option }}">
                    <input type="text" name="correct_answer[]" value="{{ correct_answer }}">
                {% endfor %}
                <button type="submit">Save</button>
            </form>
        ''', quiz=quiz, questions=questions)
        return edit_form

@app.route('/quiz/delete/<quiz_id>', methods=['POST'])
def delete_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    conn.execute('DELETE FROM quizzes WHERE id = ?', (quiz_id,))
    conn.execute('DELETE FROM questions WHERE quiz_id = ?', (quiz_id,))
    conn.execute('DELETE FROM results WHERE quiz_id = ?', (quiz_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/quiz/<quiz_id>', methods=['GET', 'POST'])
def take_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    if request.method == 'POST':
        answers = request.form.getlist('answer[]')
        score = 0
        correct_answers = []
        conn = get_db_connection()
        questions = conn.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
        for question, answer in zip(questions, answers):
            if answer == question['correct_answer']:
                score += 1
                correct_answers.append(True)
            else:
                correct_answers.append(False)
        conn.execute('INSERT INTO results (user_id, quiz_id, score) VALUES (?, ?, ?)', (user_id, quiz_id, score))
        conn.commit()
        conn.close()
        return render_template_string('''
            <h1>Quiz Results</h1>
            <p>Score: {{ score }}</p>
            {% for question, correct in zip(questions, correct_answers) %}
                <p>{{ question.question }}</p>
                {% if correct %}
                    <p>Correct</p>
                {% else %}
                    <p>Incorrect</p>
                {% endif %}
            {% endfor %}
        ''', score=score, questions=questions, correct_answers=correct_answers)
    else:
        conn = get_db_connection()
        questions = conn.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
        conn.close()
        quiz_form = render_template_string('''
            <form method="post">
                {% for question in questions %}
                    <p>{{ question.question }}</p>
                    <input type="radio" name="answer[{{ loop.index0 }}]" value="{{ question.options[0] }}">
                    <input type="radio" name="answer[{{ loop.index0 }}]" value="{{ question.options[1] }}">
                    <input type="radio" name="answer[{{ loop.index0 }}]" value="{{ question.options[2] }}">
                    <input type="radio" name="answer[{{ loop.index0 }}]" value="{{ question.options[3] }}">
                {% endfor %}
                <button type="submit">Submit</button>
            </form>
        ''', questions=questions)
        return quiz_form

@app.route('/quiz/results/<quiz_id>')
def quiz_results(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    result = conn.execute('SELECT * FROM results WHERE user_id = ? AND quiz_id = ?', (user_id, quiz_id)).fetchone()
    conn.close()
    return render_template_string('''
        <h1>Quiz Results</h1>
        <p>Score: {{ result.score }}</p>
    ''', result=result)

@app.route('/quiz/leaderboard')
def quiz_leaderboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    results = conn.execute('SELECT * FROM results ORDER BY score DESC').fetchall()
    conn.close()
    return render_template_string('''
        <h1>Quiz Leaderboard</h1>
        <table>
            <tr>
                <th>User ID</th>
                <th>Score</th>
            </tr>
            {% for result in results %}
                <tr>
                    <td>{{ result.user_id }}</td>
                    <td>{{ result.score }}</td>
                </tr>
            {% endfor %}
        </table>
    ''', results=results)

if __name__ == '__main__':
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            is_admin BOOLEAN
        );
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER,
            question TEXT,
            options TEXT,
            correct_answer TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        );
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            quiz_id INTEGER,
            score INTEGER,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        );
    ''')
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    conn.execute("INSERT INTO quizzes (user_id, title, description) VALUES (?, ?, ?)", (1, 'Math Quiz', 'Basic mathematics questions'))
    conn.execute("INSERT INTO quizzes (user_id, title, description) VALUES (?, ?, ?)", (2, 'Science Quiz', 'General science questions'))
    conn.execute("INSERT INTO questions (quiz_id, question, options, correct_answer) VALUES (?, ?, ?, ?)", (1, 'What is 2+2?', '["3","4","5","6"]', '4'))
    conn.execute("INSERT INTO questions (quiz_id, question, options, correct_answer) VALUES (?, ?, ?, ?)", (1, 'What is 3*3?', '["6","7","8","9"]', '9'))
    conn.commit()
    conn.close()
    app.run(debug=True)