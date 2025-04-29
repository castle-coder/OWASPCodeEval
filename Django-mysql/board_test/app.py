from flask import Flask, request, session, render_template_string, redirect, url_for, flash
import pymysql
import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'mock_user',
    'password': 'mock_password',
    'db': 'mock_db'
}

# Create tables and insert test data
def init_db():
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50),
            is_admin BOOLEAN
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boards (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            title VARCHAR(255),
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            is_blocked BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id INT PRIMARY KEY AUTO_INCREMENT,
            post_id INT,
            user_id INT,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES boards(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Insert test data
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (%s, %s, %s)", (1, 'First Post', 'This is the first post.'))
    cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (%s, %s, %s)", (2, 'Admin Post', 'This post was written by an admin.'))
    conn.commit()
    conn.close()

# Initialize database
init_db()

@app.route('/login/<user_id>', methods=['GET'])
def login(user_id):
    session['user_id'] = user_id
    return redirect(url_for('board'))

@app.route('/board', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))
    
    title = request.form['title']
    content = request.form['content']
    user_id = session['user_id']
    
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (%s, %s, %s)", (user_id, title, content))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('board'))

@app.route('/board/edit/<post_id>', methods=['POST'])
def edit_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))
    
    title = request.form['title']
    content = request.form['content']
    user_id = session['user_id']
    
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE boards SET title=%s, content=%s, updated_at=NOW() WHERE id=%s AND user_id=%s", (title, content, post_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('board'))

@app.route('/board/delete/<post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))
    
    user_id = session['user_id']
    
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE boards SET is_blocked=TRUE, updated_at=NOW() WHERE id=%s AND user_id=%s", (post_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('board'))

@app.route('/board/<post_id>', methods=['GET'])
def view_post(post_id):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM boards WHERE id=%s", (post_id,))
    post = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if post is None:
        return "Post not found"
    
    return render_template_string('''
        <h1>{{ post.title }}</h1>
        <p>{{ post.content }}</p>
        <p>Created on: {{ post.created_at }}</p>
        <p>Updated on: {{ post.updated_at }}</p>
    ''', post=post)

@app.route('/admin/block/<post_id>', methods=['POST'])
def block_post(post_id):
    if 'user_id' not in session or not session['user_id'] == 2:
        return redirect(url_for('login', user_id=1))
    
    user_id = session['user_id']
    
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE boards SET is_blocked=TRUE, updated_at=NOW() WHERE id=%s AND user_id=%s", (post_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('board'))

@app.route('/board/report/<post_id>', methods=['POST'])
def report_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))
    
    user_id = session['user_id']
    reason = request.form['reason']
    
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reports (post_id, user_id, reason) VALUES (%s, %s, %s)", (post_id, user_id, reason))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('board'))

@app.route('/')
def board():
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM boards")
    posts = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template_string('''
        <h1>Community Board</h1>
        <form method="POST" action="/board">
            <label>Title:</label><br>
            <input type="text" name="title"><br>
            <label>Content:</label><br>
            <textarea name="content"></textarea><br>
            <input type="submit" value="Create Post">
        </form>
        <ul>
            {% for post in posts %}
            <li>
                <h2><a href="/board/{{ post.id }}">{{ post.title }}</a></h2>
                <p>{{ post.content }}</p>
                {% if session.user_id == post.user_id %}
                <form method="POST" action="/board/edit/{{ post.id }}">
                    <input type="text" name="title" value="{{ post.title }}">
                    <textarea name="content">{{ post.content }}</textarea>
                    <input type="submit" value="Edit">
                </form>
                <form method="POST" action="/board/delete/{{ post.id }}">
                    <input type="submit" value="Delete">
                </form>
                {% endif %}
                <form method="POST" action="/admin/block/{{ post.id }}">
                    <input type="submit" value="Block (Admin Only)">
                </form>
                <form method="POST" action="/board/report/{{ post.id }}">
                    <label>Reason:</label><br>
                    <textarea name="reason"></textarea><br>
                    <input type="submit" value="Report">
                </form>
            </li>
            {% endfor %}
        </ul>
    ''', posts=posts)

if __name__ == '__main__':
    app.run(debug=True)