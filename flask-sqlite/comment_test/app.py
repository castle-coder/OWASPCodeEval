from flask import Flask, request, session, render_template_string, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mock_db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.before_first_request
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            parent_id INTEGER,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (parent_id) REFERENCES comments(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            comment_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_resolved INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (comment_id) REFERENCES comments(id)
        )
    ''')
    conn.execute('''
        INSERT INTO users (username, is_admin) VALUES ('user', 0)
    ''')
    conn.execute('''
        INSERT INTO users (username, is_admin) VALUES ('admin', 1)
    ''')
    conn.execute('''
        INSERT INTO posts (title, content) VALUES ('First Post', 'Welcome to our site')
    ''')
    conn.execute('''
        INSERT INTO comments (user_id, post_id, content) VALUES (1, 1, 'First comment')
    ''')
    conn.execute('''
        INSERT INTO comments (user_id, post_id, parent_id, content) VALUES (2, 1, 1, 'Reply to comment')
    ''')
    conn.commit()
    conn.close()

@app.route('/index')
def index():
    return render_template_string('''
        <h1>Welcome to the Comment Web Service</h1>
        <a href="/login/1">Login as User</a>
        <a href="/login/2">Login as Admin</a>
    ''')

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = user_id == '2'
    return redirect(url_for('index'))

@app.route('/comment/create', methods=['POST'])
def create_comment():
    user_id = session.get('user_id')
    if not user_id:
        return 'Not logged in', 401
    post_id = request.form['post_id']
    content = request.form['content']
    parent_id = request.form.get('parent_id')
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO comments (user_id, post_id, parent_id, content) VALUES (?, ?, ?, ?)
    ''', (user_id, post_id, parent_id, content))
    conn.commit()
    conn.close()
    return redirect(url_for('view_comments', post_id=post_id))

@app.route('/comment/edit/<comment_id>', methods=['POST'])
def edit_comment(comment_id):
    user_id = session.get('user_id')
    if not user_id:
        return 'Not logged in', 401
    content = request.form['content']
    conn = get_db_connection()
    conn.execute('''
        UPDATE comments SET content = ?, updated_at = ? WHERE id = ? AND user_id = ?
    ''', (content, datetime.now(), comment_id, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('view_comments', post_id=request.form['post_id']))

@app.route('/comment/delete/<comment_id>', methods=['POST'])
def delete_comment(comment_id):
    user_id = session.get('user_id')
    if not user_id:
        return 'Not logged in', 401
    conn = get_db_connection()
    conn.execute('''
        UPDATE comments SET is_deleted = 1 WHERE id = ? AND user_id = ?
    ''', (comment_id, user_id))
    conn.execute('''
        UPDATE comments SET is_deleted = 1 WHERE parent_id = ?
    ''', (comment_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('view_comments', post_id=request.form['post_id']))

@app.route('/post/<post_id>/comments')
def view_comments(post_id):
    conn = get_db_connection()
    comments = conn.execute('''
        SELECT * FROM comments WHERE post_id = ? AND is_deleted = 0 ORDER BY created_at DESC
    ''', (post_id,)).fetchall()
    conn.close()
    return render_template_string('''
        <h1>Comments for Post {{ post_id }}</h1>
        {% for comment in comments %}
            <div>
                <p>{{ comment.content }}</p>
                <p>Created by: {{ comment.user_id }}</p>
                <p>Created at: {{ comment.created_at }}</p>
                {% if comment.user_id == session.user_id %}
                    <form action="/comment/edit/{{ comment.id }}" method="post">
                        <input type="hidden" name="post_id" value="{{ post_id }}">
                        <input type="text" name="content" value="{{ comment.content }}">
                        <button type="submit">Edit</button>
                    </form>
                    <form action="/comment/delete/{{ comment.id }}" method="post">
                        <input type="hidden" name="post_id" value="{{ post_id }}">
                        <button type="submit">Delete</button>
                    </form>
                {% endif %}
            </div>
        {% endfor %}
        <form action="/comment/create" method="post">
            <input type="hidden" name="post_id" value="{{ post_id }}">
            <input type="text" name="content" placeholder="Add a comment">
            <button type="submit">Submit</button>
        </form>
    ''', post_id=post_id, comments=comments)

@app.route('/admin/block/<comment_id>', methods=['POST'])
def block_comment(comment_id):
    if not session.get('is_admin'):
        return 'Not authorized', 403
    conn = get_db_connection()
    conn.execute('''
        UPDATE comments SET is_blocked = 1 WHERE id = ?
    ''', (comment_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('view_comments', post_id=request.form['post_id']))

@app.route('/comment/report/<comment_id>', methods=['POST'])
def report_comment(comment_id):
    user_id = session.get('user_id')
    if not user_id:
        return 'Not logged in', 401
    reason = request.form['reason']
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO reports (user_id, comment_id, reason) VALUES (?, ?, ?)
    ''', (user_id, comment_id, reason))
    conn.commit()
    conn.close()
    return redirect(url_for('view_comments', post_id=request.form['post_id']))

if __name__ == '__main__':
    app.run(use_reloader=False)