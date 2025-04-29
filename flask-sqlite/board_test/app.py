from flask import Flask, request, session, render_template_string, redirect, url_for, abort
import sqlite3
from datetime import datetime
import os
from markupsafe import escape  # 입력값 escape 처리용

app = Flask(__name__)
app.secret_key = os.urandom(24)

DB_PATH = 'mock_db.sqlite3'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                is_admin BOOLEAN
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS boards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_blocked BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER,
                user_id INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES boards(id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)
        # 중복 삽입 방지
        users = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        if users['cnt'] == 0:
            conn.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
            conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
            conn.execute("INSERT INTO boards (user_id, title, content) VALUES (1, 'First Post', 'This is the first post.')")
            conn.execute("INSERT INTO boards (user_id, title, content) VALUES (2, 'Admin Post', 'This post was written by an admin.')")
        conn.commit()

@app.route('/login/<int:user_id>')
def login(user_id):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not user:
        return "User not found", 404
    session['user_id'] = user['user_id']
    session['is_admin'] = user['is_admin']
    return redirect(url_for('board'))

@app.route('/board', methods=['GET'])
def board():
    with get_db_connection() as conn:
        posts = conn.execute("SELECT * FROM boards WHERE is_blocked = 0").fetchall()
    return render_template_string("""
        <h1>Community Board</h1>
        {% for post in posts %}
            <a href="{{ url_for('view_post', post_id=post['id']) }}">{{ post['title'] | e }}</a><br>
        {% endfor %}
        <form method="POST" action="{{ url_for('create_post') }}">
            <input type="text" name="title" placeholder="Title" required>
            <textarea name="content" placeholder="Content" required></textarea>
            <button type="submit">Create Post</button>
        </form>
    """, posts=posts)

@app.route('/board', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        abort(401)
    # 입력값 escape 처리
    title = escape(request.form['title'].strip())
    content = escape(request.form['content'].strip())
    with get_db_connection() as conn:
        conn.execute("INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)",
                     (session['user_id'], title, content))
        conn.commit()
    return redirect(url_for('board'))

@app.route('/board/<int:post_id>')
def view_post(post_id):
    with get_db_connection() as conn:
        post = conn.execute("SELECT * FROM boards WHERE id = ?", (post_id,)).fetchone()
    if not post or post['is_blocked']:
        return "Post not found or blocked", 404
    return render_template_string("""
        <h1>{{ post['title'] | e }}</h1>
        <p>{{ post['content'] | e }}</p>
        <a href="{{ url_for('board') }}">Back to board</a>
    """, post=post)

@app.route('/board/edit/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'user_id' not in session:
        abort(401)

    with get_db_connection() as conn:
        post = conn.execute("SELECT * FROM boards WHERE id=?", (post_id,)).fetchone()

    if not post or post['user_id'] != session['user_id']:
        abort(403)

    if request.method == 'POST':
        title = escape(request.form['title'].strip())
        content = escape(request.form['content'].strip())
        with get_db_connection() as conn:
            conn.execute("UPDATE boards SET title=?, content=?, updated_at=? WHERE id=?",
                         (title, content, datetime.now(), post_id))
            conn.commit()
        return redirect(url_for('board'))

    return render_template_string("""
        <form method="POST">
            <input type="text" name="title" value="{{ post['title'] | e }}" required><br>
            <textarea name="content" required>{{ post['content'] | e }}</textarea><br>
            <button type="submit">Save</button>
        </form>
    """, post=post)

@app.route('/board/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user_id' not in session:
        abort(401)

    with get_db_connection() as conn:
        post = conn.execute("SELECT * FROM boards WHERE id=?", (post_id,)).fetchone()
        if not post or post['user_id'] != session['user_id']:
            abort(403)
        conn.execute("UPDATE boards SET is_blocked=1 WHERE id=?", (post_id,))
        conn.commit()

    return redirect(url_for('board'))

@app.route('/admin/block/<int:post_id>', methods=['POST'])
def block_post(post_id):
    if 'user_id' not in session or not session.get('is_admin', False):
        abort(403)

    with get_db_connection() as conn:
        conn.execute("UPDATE boards SET is_blocked=1 WHERE id=?", (post_id,))
        conn.commit()

    return redirect(url_for('board'))

@app.route('/board/report/<int:post_id>', methods=['POST'])
def report_post(post_id):
    if 'user_id' not in session:
        abort(401)
    # 신고 reason도 escape
    reason = escape(request.form['reason'].strip())
    with get_db_connection() as conn:
        conn.execute("INSERT INTO reports (post_id, user_id, reason) VALUES (?, ?, ?)",
                     (post_id, session['user_id'], reason))
        conn.commit()
    return redirect(url_for('board'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
