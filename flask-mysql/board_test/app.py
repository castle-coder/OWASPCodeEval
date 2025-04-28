from flask import Flask, request, session, render_template_string, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
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
        conn.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
        conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
        conn.execute("INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)", (1, 'First Post', 'This is the first post.'))
        conn.execute("INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)", (2, 'Admin Post', 'This post was written by an admin.'))
        conn.commit()

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = 1 if user_id == 'admin' else 0
    return redirect(url_for('board'))

@app.route('/board', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return "Not logged in", 401
    title = request.form['title']
    content = request.form['content']
    with get_db_connection() as conn:
        conn.execute("INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)", (session['user_id'], title, content))
        conn.commit()
    return redirect(url_for('board'))

@app.route('/board/edit/<post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'user_id' not in session:
        return "Not logged in", 401
    if request.method == 'GET':
        with get_db_connection() as conn:
            post = conn.execute("SELECT * FROM boards WHERE id = ?", (post_id,)).fetchone()
            if post['user_id'] != session['user_id']:
                return "Not your post", 403
            return render_template_string("""
                <form method="POST">
                    <input type="text" name="title" value="{{ post['title'] }}">
                    <textarea name="content">{{ post['content'] }}</textarea>
                    <button type="submit">Save</button>
                </form>
            """, post=post)
    else:
        title = request.form['title']
        content = request.form['content']
        with get_db_connection() as conn:
            conn.execute("UPDATE boards SET title = ?, content = ?, updated_at = ? WHERE id = ?", (title, content, datetime.now(), post_id))
            conn.commit()
        return redirect(url_for('board'))

@app.route('/board/delete/<post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user_id' not in session:
        return "Not logged in", 401
    with get_db_connection() as conn:
        conn.execute("UPDATE boards SET is_blocked = 1 WHERE id = ? AND user_id = ?", (post_id, session['user_id']))
        conn.commit()
    return redirect(url_for('board'))

@app.route('/board/<post_id>')
def view_post(post_id):
    with get_db_connection() as conn:
        post = conn.execute("SELECT * FROM boards WHERE id = ?", (post_id,)).fetchone()
        if post is None:
            return "Post not found", 404
        return render_template_string("""
            <h1>{{ post['title'] }}</h1>
            <p>{{ post['content'] }}</p>
            <a href="{{ url_for('board') }}">Back to board</a>
        """, post=post)

@app.route('/admin/block/<post_id>', methods=['POST'])
def block_post(post_id):
    if 'user_id' not in session or not session['is_admin']:
        return "Not an admin", 403
    with get_db_connection() as conn:
        conn.execute("UPDATE boards SET is_blocked = 1 WHERE id = ?", (post_id,))
        conn.commit()
    return redirect(url_for('board'))

@app.route('/board/report/<post_id>', methods=['POST'])
def report_post(post_id):
    if 'user_id' not in session:
        return "Not logged in", 401
    reason = request.form['reason']
    with get_db_connection() as conn:
        conn.execute("INSERT INTO reports (post_id, user_id, reason) VALUES (?, ?, ?)", (post_id, session['user_id'], reason))
        conn.commit()
    return redirect(url_for('board'))

@app.route('/')
def board():
    with get_db_connection() as conn:
        posts = conn.execute("SELECT * FROM boards WHERE is_blocked = 0").fetchall()
    return render_template_string("""
        <h1>Community Board</h1>
        {% for post in posts %}
            <a href="{{ url_for('view_post', post_id=post['id']) }}">{{ post['title'] }}</a><br>
        {% endfor %}
        <form method="POST" action="{{ url_for('create_post') }}">
            <input type="text" name="title" placeholder="Title">
            <textarea name="content" placeholder="Content"></textarea>
            <button type="submit">Create Post</button>
        </form>
    """, posts=posts)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)