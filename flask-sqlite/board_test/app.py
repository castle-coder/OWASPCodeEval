from flask import Flask, request, session, render_template_string, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATABASE = 'mock_db.sqlite3'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def before_request():
    db = get_db_connection()
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            is_admin BOOLEAN
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES boards(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    db.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    db.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    db.execute("INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)", (1, 'First Post', 'This is the first post.'))
    db.execute("INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)", (2, 'Admin Post', 'This post was written by an admin.'))
    db.commit()
    db.close()

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = user_id == 'admin'
    return redirect(url_for('index'))

@app.route('/board', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return "Unauthorized", 401
    title = request.form['title']
    content = request.form['content']
    db = get_db_connection()
    db.execute('INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)', (session['user_id'], title, content))
    db.commit()
    db.close()
    return redirect(url_for('index'))

@app.route('/board/edit/<post_id>', methods=['POST'])
def edit_post(post_id):
    if 'user_id' not in session:
        return "Unauthorized", 401
    title = request.form['title']
    content = request.form['content']
    db = get_db_connection()
    db.execute('UPDATE boards SET title = ?, content = ?, updated_at = ? WHERE id = ? AND user_id = ?', (title, content, datetime.now(), post_id, session['user_id']))
    db.commit()
    db.close()
    return redirect(url_for('index'))

@app.route('/board/delete/<post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user_id' not in session:
        return "Unauthorized", 401
    db = get_db_connection()
    db.execute('UPDATE boards SET is_blocked = 1 WHERE id = ? AND user_id = ?', (post_id, session['user_id']))
    db.commit()
    db.close()
    return redirect(url_for('index'))

@app.route('/board/<post_id>')
def view_post(post_id):
    db = get_db_connection()
    post = db.execute('SELECT * FROM boards WHERE id = ?', (post_id,)).fetchone()
    db.close()
    if post:
        return render_template_string('''
            <h1>{{ post.title }}</h1>
            <p>{{ post.content }}</p>
        ''', post=post)
    else:
        return "Post not found", 404

@app.route('/admin/block/<post_id>', methods=['POST'])
def block_post(post_id):
    if 'user_id' not in session or not session['is_admin']:
        return "Unauthorized", 401
    db = get_db_connection()
    db.execute('UPDATE boards SET is_blocked = 1 WHERE id = ?', (post_id,))
    db.commit()
    db.close()
    return redirect(url_for('index'))

@app.route('/board/report/<post_id>', methods=['POST'])
def report_post(post_id):
    if 'user_id' not in session:
        return "Unauthorized", 401
    reason = request.form['reason']
    db = get_db_connection()
    db.execute('INSERT INTO reports (post_id, user_id, reason) VALUES (?, ?, ?)', (post_id, session['user_id'], reason))
    db.commit()
    db.close()
    return redirect(url_for('index'))

@app.route('/')
def index():
    db = get_db_connection()
    posts = db.execute('SELECT * FROM boards WHERE is_blocked = 0').fetchall()
    db.close()
    return render_template_string('''
        <h1>Board</h1>
        <ul>
            {% for post in posts %}
                <li><a href="/board/{{ post.id }}">{{ post.title }}</a></li>
            {% endfor %}
        </ul>
        {% if session.user_id %}
            <h2>Create Post</h2>
            <form method="post" action="/board">
                <input type="text" name="title" placeholder="Title" required>
                <textarea name="content" placeholder="Content" required></textarea>
                <button type="submit">Create</button>
            </form>
        {% endif %}
    ''', posts=posts)

if __name__ == '__main__':
    app.run(debug=True)