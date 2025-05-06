from flask import Flask, request, session, redirect, url_for, render_template_string
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATABASE = 'mock_db.sqlite3'

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            is_admin BOOLEAN
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER,
            text TEXT,
            is_blocked BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS options (
            option_id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER,
            text TEXT,
            is_correct BOOLEAN,
            FOREIGN KEY (question_id) REFERENCES questions(question_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS results (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER,
            user_id INTEGER,
            score INTEGER,
            total INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES questions(question_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = False
    if user_id == '2':
        session['is_admin'] = True
    return redirect(url_for('index'))

@app.route('/quiz', methods=['POST'])
def create_quiz():
    if 'user_id' not in session:
        return "Not logged in", 401
    title = request.form['title']
    description = request.form['description']
    conn = get_db_connection()
    conn.execute('INSERT INTO quizzes (user_id, title, description) VALUES (?, ?, ?)', (session['user_id'], title, description))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/quiz/<quiz_id>/question', methods=['POST'])
def add_question(quiz_id):
    if 'user_id' not in session:
        return "Not logged in", 401
    text = request.form['text']
    options = request.form.getlist('options[]')
    correct = request.form.getlist('correct[]')
    conn = get_db_connection()
    question_id = conn.execute('INSERT INTO questions (quiz_id, text) VALUES (?, ?)', (quiz_id, text)).lastrowid
    for i, opt in enumerate(options):
        is_correct = correct[i] == 'true'
        conn.execute('INSERT INTO options (question_id, text, is_correct) VALUES (?, ?, ?)', (question_id, opt, is_correct))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/quiz/edit/<quiz_id>', methods=['POST'])
def edit_quiz(quiz_id):
    if 'user_id' not in session:
        return "Not logged in", 401
    title = request.form['title']
    description = request.form['description']
    conn = get_db_connection()
    conn.execute('UPDATE quizzes SET title = ?, description = ?, updated_at = ? WHERE quiz_id = ? AND user_id = ?', (title, description, datetime.now(), quiz_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/quiz/<quiz_id>/question/edit/<question_id>', methods=['POST'])
def edit_question(quiz_id, question_id):
    if 'user_id' not in session:
        return "Not logged in", 401
    text = request.form['text']
    options = request.form.getlist('options[]')
    correct = request.form.getlist('correct[]')
    conn = get_db_connection()
    conn.execute('UPDATE questions SET text = ?, updated_at = ? WHERE question_id = ? AND quiz_id = ? AND user_id = ?', (text, datetime.now(), question_id, quiz_id, session['user_id']))
    conn.execute('DELETE FROM options WHERE question_id = ?', (question_id,))
    for i, opt in enumerate(options):
        is_correct = correct[i] == 'true'
        conn.execute('INSERT INTO options (question_id, text, is_correct) VALUES (?, ?, ?)', (question_id, opt, is_correct))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/quiz/delete/<quiz_id>', methods=['POST'])
def delete_quiz(quiz_id):
    if 'user_id' not in session:
        return "Not logged in", 401
    conn = get_db_connection()
    conn.execute('UPDATE quizzes SET is_deleted = 1 WHERE quiz_id = ? AND user_id = ?', (quiz_id, session['user_id']))
    conn.execute('UPDATE questions SET is_deleted = 1 WHERE quiz_id = ? AND user_id = ?', (quiz_id, session['user_id']))
    conn.execute('UPDATE results SET is_deleted = 1 WHERE quiz_id = ? AND user_id = ?', (quiz_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/quiz/<quiz_id>/question/delete/<question_id>', methods=['POST'])
def delete_question(quiz_id, question_id):
    if 'user_id' not in session:
        return "Not logged in", 401
    conn = get_db_connection()
    conn.execute('UPDATE questions SET is_deleted = 1 WHERE question_id = ? AND quiz_id = ? AND user_id = ?', (question_id, quiz_id, session['user_id']))
    conn.execute('UPDATE options SET is_deleted = 1 WHERE question_id = ?', (question_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/quiz/<quiz_id>/take', methods=['GET', 'POST'])
def take_quiz(quiz_id):
    if 'user_id' not in session:
        return "Not logged in", 401
    if request.method == 'GET':
        conn = get_db_connection()
        questions = conn.execute('SELECT * FROM questions WHERE quiz_id = ? AND is_deleted = 0', (quiz_id,)).fetchall()
        options = conn.execute('SELECT * FROM options WHERE question_id IN (SELECT question_id FROM questions WHERE quiz_id = ? AND is_deleted = 0)', (quiz_id,)).fetchall()
        conn.close()
        return render_template_string('''
            <form action="{{ url_for('take_quiz', quiz_id=quiz_id) }}" method="POST">
                {% for q in questions %}
                    <h3>{{ q['text'] }}</h3>
                    {% for o in options %}
                        {% if o['question_id'] == q['question_id'] %}
                            <input type="radio" name="answer_{{ q['question_id'] }}" value="{{ o['option_id'] }}">{{ o['text'] }}<br>
                        {% endif %}
                    {% endfor %}
                {% endfor %}
                <input type="submit" value="Submit">
            </form>
        ''', quiz_id=quiz_id)
    else:
        answers = {}
        for q in request.form:
            if q.startswith('answer_'):
                question_id = int(q.split('_')[1])
                answers[question_id] = int(request.form[q])
        conn = get_db_connection()
        questions = conn.execute('SELECT * FROM questions WHERE quiz_id = ? AND is_deleted = 0', (quiz_id,)).fetchall()
        correct_answers = 0
        for q in questions:
            options = conn.execute('SELECT * FROM options WHERE question_id = ?', (q['question_id'],)).fetchall()
            for o in options:
                if o['is_correct'] and o['option_id'] == answers[q['question_id']]:
                    correct_answers += 1
                    break
        score = correct_answers * 100 // len(questions)
        conn.execute('INSERT INTO results (quiz_id, user_id, score, total) VALUES (?, ?, ?, ?)', (quiz_id, session['user_id'], score, len(questions)))
        conn.commit()
        conn.close()
        return f"Your score is {score}%"

@app.route('/quiz/<quiz_id>/results')
def view_results(quiz_id):
    if 'user_id' not in session:
        return "Not logged in", 401
    if session['is_admin']:
        conn = get_db_connection()
        results = conn.execute('SELECT * FROM results WHERE quiz_id = ? AND is_deleted = 0', (quiz_id,)).fetchall()
        conn.close()
        return render_template_string('''
            <table>
                <tr><th>User ID</th><th>Score</th><th>Total</th><th>Created At</th></tr>
                {% for r in results %}
                    <tr><td>{{ r['user_id'] }}</td><td>{{ r['score'] }}</td><td>{{ r['total'] }}</td><td>{{ r['created_at'] }}</td></tr>
                {% endfor %}
            </table>
        ''', results=results)
    else:
        conn = get_db_connection()
        results = conn.execute('SELECT * FROM results WHERE quiz_id = ? AND user_id = ? AND is_deleted = 0', (quiz_id, session['user_id'])).fetchall()
        conn.close()
        return render_template_string('''
            <table>
                <tr><th>Score</th><th>Total</th><th>Created At</th></tr>
                {% for r in results %}
                    <tr><td>{{ r['score'] }}</td><td>{{ r['total'] }}</td><td>{{ r['created_at'] }}</td></tr>
                {% endfor %}
            </table>
        ''', results=results)

@app.route('/admin/block/question/<question_id>', methods=['POST'])
def block_question(question_id):
    if 'user_id' not in session or not session['is_admin']:
        return "Not logged in or not admin", 401
    conn = get_db_connection()
    conn.execute('UPDATE questions SET is_blocked = 1 WHERE question_id = ?', (question_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/quiz/<quiz_id>/report/<question_id>', methods=['POST'])
def report_question(quiz_id, question_id):
    if 'user_id' not in session:
        return "Not logged in", 401
    reason = request.form['reason']
    conn = get_db_connection()
    conn.execute('INSERT INTO reports (question_id, user_id, reason) VALUES (?, ?, ?)', (question_id, session['user_id'], reason))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)