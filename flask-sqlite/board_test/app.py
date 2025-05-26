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

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = user_id == 'admin'
    return redirect(url_for('board'))

@app.route('/board', methods=['GET', 'POST'])
def board():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        conn = get_db_connection()
        conn.execute('INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)', (session['user_id'], title, content))
        conn.commit()
        conn.close()
        return redirect(url_for('board'))
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM boards WHERE is_blocked = 0').fetchall()
    conn.close()
    return render_template_string('''
        <h1>Board</h1>
        <form method="post">
            <input type="text" name="title" placeholder="Title" required>
            <textarea name="content" placeholder="Content" required></textarea>
            <button type="submit">Create Post</button>
        </form>
        <ul>
            {% for post in posts %}
            <li>
                <h2>{{ post['title'] }}</h2>
                <p>{{ post['content'] }}</p>
                <a href="{{ url_for('post', post_id=post['id']) }}">View</a>
                {% if post['user_id'] == session['user_id'] %}
                <a href="{{ url_for('edit_post', post_id=post['id']) }}">Edit</a>
                <a href="{{ url_for('delete_post', post_id=post['id']) }}">Delete</a>
                {% endif %}
                {% if session['is_admin'] %}
                <a href="{{ url_for('block_post', post_id=post['id']) }}">Block</a>
                {% endif %}
            </li>
            {% endfor %}
        </ul>
    ''', posts=posts)

@app.route('/board/<post_id>')
def post(post_id):
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM boards WHERE id = ?', (post_id,)).fetchone()
    conn.close()
    return render_template_string('''
        <h1>{{ post['title'] }}</h1>
        <p>{{ post['content'] }}</p>
        <a href="{{ url_for('board') }}">Back to Board</a>
    ''', post=post)

@app.route('/board/edit/<post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        conn = get_db_connection()
        conn.execute('UPDATE boards SET title = ?, content = ?, updated_at = ? WHERE id = ?', (title, content, datetime.now(), post_id))
        conn.commit()
        conn.close()
        return redirect(url_for('board'))
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM boards WHERE id = ?', (post_id,)).fetchone()
    conn.close()
    return render_template_string('''
        <h1>Edit Post</h1>
        <form method="post">
            <input type="text" name="title" value="{{ post['title'] }}" required>
            <textarea name="content" required>{{ post['content'] }}</textarea>
            <button type="submit">Update Post</button>
        </form>
        <a href="{{ url_for('board') }}">Back to Board</a>
    ''', post=post)

@app.route('/board/delete/<post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    conn = get_db_connection()
    conn.execute('UPDATE boards SET is_blocked = 1 WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('board'))

@app.route('/admin/block/<post_id>', methods=['POST'])
def block_post(post_id):
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('login', user_id='user'))
    conn = get_db_connection()
    conn.execute('UPDATE boards SET is_blocked = 1 WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('board'))

@app.route('/board/report/<post_id>', methods=['POST'])
def report_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    reason = request.form['reason']
    conn = get_db_connection()
    conn.execute('INSERT INTO reports (post_id, user_id, reason) VALUES (?, ?, ?)', (post_id, session['user_id'], reason))
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