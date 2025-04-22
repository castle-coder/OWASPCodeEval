
from flask import Flask, request, session, render_template_string, redirect, url_for
import pymysql

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key

# Database connection configuration
db_config = {
    'host': 'localhost',
    'user': 'mock_user',
    'password': 'mock_password',
    'db': 'mock_db'
}

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    return redirect(url_for('board'))

@app.route('/board', methods=['GET', 'POST'])
def board():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        user_id = session['user_id']
        
        with pymysql.connect(**db_config) as connection:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (%s, %s, %s)", (user_id, title, content))
            connection.commit()
        
        return redirect(url_for('board'))
    
    posts = get_posts()
    return render_template_string("""
    <h1>Bulletin Board</h1>
    <a href="{{ url_for('login', user_id='user') }}">Login</a>
    <hr>
    <form method="POST">
        <label for="title">Title:</label>
        <input type="text" id="title" name="title">
        <label for="content">Content:</label>
        <textarea id="content" name="content"></textarea>
        <button type="submit">Create Post</button>
    </form>
    <hr>
    <h2>Posts</h2>
    {% for post in posts %}
        <div>
            <h3>{{ post['title'] }}</h3>
            <p>{{ post['content'] }}</p>
            {% if post['user_id'] == session['user_id'] or session['user_id'] == 'admin' %}
                <form method="POST" action="{{ url_for('edit', post_id=post['id']) }}">
                    <button type="submit">Edit</button>
                </form>
                <form method="POST" action="{{ url_for('delete', post_id=post['id']) }}">
                    <button type="submit">Delete</button>
                </form>
            {% endif %}
        </div>
    {% endfor %}
    """, posts=posts)

@app.route('/board/edit/<post_id>', methods=['POST'])
def edit(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    title = request.form['title']
    content = request.form['content']
    user_id = session['user_id']
    
    with pymysql.connect(**db_config) as connection:
        cursor = connection.cursor()
        cursor.execute("UPDATE boards SET title=%s, content=%s, updated_at=NOW() WHERE id=%s AND user_id=%s", (title, content, post_id, user_id))
        connection.commit()
    
    return redirect(url_for('board'))

@app.route('/board/delete/<post_id>', methods=['POST'])
def delete(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    user_id = session['user_id']
    
    with pymysql.connect(**db_config) as connection:
        cursor = connection.cursor()
        cursor.execute("UPDATE boards SET is_deleted=1, updated_at=NOW() WHERE id=%s AND user_id=%s", (post_id, user_id))
        connection.commit()
    
    return redirect(url_for('board'))

@app.route('/board/<post_id>')
def view_post(post_id):
    with pymysql.connect(**db_config) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM boards WHERE id=%s", (post_id,))
        post = cursor.fetchone()
        if post is None:
            return "Post not found"
    
    return render_template_string("""
    <h1>Post</h1>
    <p><strong>Title:</strong> {{ post.title }}</p>
    <p>{{ post.content }}</p>
    """, post=post)

@app.route('/admin/block/<post_id>', methods=['POST'])
def block_post(post_id):
    if 'user_id' not in session or session['user_id'] != 'admin':
        return redirect(url_for('board'))
    
    with pymysql.connect(**db_config) as connection:
        cursor = connection.cursor()
        cursor.execute("UPDATE boards SET is_blocked=1, updated_at=NOW() WHERE id=%s", (post_id,))
        connection.commit()
    
    return redirect(url_for('board'))

@app.route('/board/report/<post_id>', methods=['POST'])
def report_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    reason = request.form['reason']
    user_id = session['user_id']
    
    with pymysql.connect(**db_config) as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO reports (post_id, user_id, reason, created_at) VALUES (%s, %s, %s, NOW())", (post_id, user_id, reason))
        connection.commit()
    
    return redirect(url_for('board'))

def get_posts():
    with pymysql.connect(**db_config) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM boards WHERE is_deleted=0 ORDER BY created_at DESC")
        return cursor.fetchall()

if __name__ == '__main__':
    # Initialize the database and insert test data
    with pymysql.connect(**db_config) as connection:
        cursor = connection.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INT PRIMARY KEY, username VARCHAR(50), is_admin BOOLEAN)")
        cursor.execute("CREATE TABLE IF NOT EXISTS boards (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, title VARCHAR(255), content TEXT, created_at TIMESTAMP, updated_at TIMESTAMP, is_deleted BOOLEAN DEFAULT 0, is_blocked BOOLEAN DEFAULT 0)")
        cursor.execute("CREATE TABLE IF NOT EXISTS reports (report_id INT AUTO_INCREMENT PRIMARY KEY, post_id INT, user_id INT, reason TEXT, created_at TIMESTAMP)")
        
        # Insert test data
        cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
        cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
        cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (1, 'First Post', 'This is the first post.')")
        cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (2, 'Admin Post', 'This post was written by an admin.')")
        connection.commit()
    
    app.run(debug=True)