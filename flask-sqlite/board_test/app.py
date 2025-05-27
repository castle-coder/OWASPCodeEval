from flask import Flask, request, session, render_template_string, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def before_request():
    if 'user_id' in session:
        g.user_id = session['user_id']
        g.is_admin = session['is_admin']
    else:
        g.user_id = None
        g.is_admin = False

@app.route('/login/<user_id>', methods=['GET'])
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = user_id == 'admin'
    return redirect(url_for('board'))

@app.route('/board', methods=['POST'])
def create_post():
    if g.user_id is None:
        return "Login required", 401
    title = request.form['title']
    content = request.form['content']
    conn = get_db_connection()
    conn.execute('INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)', (g.user_id, title, content))
    conn.commit()
    conn.close()
    return redirect(url_for('board'))

@app.route('/board/edit/<post_id>', methods=['POST'])
def edit_post(post_id):
    if g.user_id is None:
        return "Login required", 401
    title = request.form['title']
    content = request.form['content']
    conn = get_db_connection()
    conn.execute('UPDATE boards SET title = ?, content = ?, updated_at = ? WHERE id = ? AND user_id = ?', (title, content, datetime.now(), post_id, g.user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('board'))

@app.route('/board/delete/<post_id>', methods=['POST'])
def delete_post(post_id):
    if g.user_id is None:
        return "Login required", 401
    conn = get_db_connection()
    conn.execute('UPDATE boards SET is_blocked = 1 WHERE id = ? AND user_id = ?', (post_id, g.user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('board'))

@app.route('/board/<post_id>', methods=['GET'])
def view_post(post_id):
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM boards WHERE id = ?', (post_id,)).fetchone()
    conn.close()
    if post is None:
        return "Post not found", 404
    return render_template_string('''
        <h1>{{ post.title }}</h1>
        <p>{{ post.content }}</p>
        {% if g.user_id == post.user_id %}
            <form action="{{ url_for('edit_post', post_id=post.id) }}" method="post">
                <input type="text" name="title" value="{{ post.title }}">
                <input type="text" name="content" value="{{ post.content }}">
                <button type="submit">Edit</button>
            </form>
            <form action="{{ url_for('delete_post', post_id=post.id) }}" method="post">
                <button type="submit">Delete</button>
            </form>
        {% endif %}
    ''', post=post)

@app.route('/admin/block/<post_id>', methods=['POST'])
def block_post(post_id):
    if not g.is_admin:
        return "Admin access required", 403
    conn = get_db_connection()
    conn.execute('UPDATE boards SET is_blocked = 1 WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('board'))

@app.route('/board/report/<post_id>', methods=['POST'])
def report_post(post_id):
    if g.user_id is None:
        return "Login required", 401
    reason = request.form['reason']
    conn = get_db_connection()
    conn.execute('INSERT INTO reports (post_id, user_id, reason) VALUES (?, ?, ?)', (post_id, g.user_id, reason))
    conn.commit()
    conn.close()
    return redirect(url_for('board'))

if __name__ == '__main__':
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, is_admin BOOLEAN)')
    conn.execute('CREATE TABLE IF NOT EXISTS boards (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_blocked BOOLEAN DEFAULT 0, FOREIGN KEY (user_id) REFERENCES users(user_id))')
    conn.execute('CREATE TABLE IF NOT EXISTS reports (report_id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER, user_id INTEGER, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (post_id) REFERENCES boards(id), FOREIGN KEY (user_id) REFERENCES users(user_id))')
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    conn.execute("INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)", (1, 'First Post', 'This is the first post.'))
    conn.execute("INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)", (2, 'Admin Post', 'This post was written by an admin.'))
    conn.commit()
    conn.close()
    app.run(debug=True)