
from flask import Flask, request, session, render_template_string, redirect, url_for
import pymysql

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database connection
connection = pymysql.connect(host='localhost', user='mock_user', password='1234', db='mock_db')

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = 1 if user_id == '2' else 0
    return redirect(url_for('index'))

@app.route('/board', methods=['POST'])
def create_post():
    user_id = session.get('user_id')
    if not user_id:
        return "Not logged in", 401

    title = request.form['title']
    content = request.form['content']

    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (%s, %s, %s)", (user_id, title, content))
        connection.commit()

    return redirect(url_for('index'))

@app.route('/board/edit/<post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    user_id = session.get('user_id')
    if not user_id:
        return "Not logged in", 401

    if request.method == 'GET':
        with connection.cursor() as cursor:
            cursor.execute("SELECT title, content FROM boards WHERE id = %s", (post_id,))
            post = cursor.fetchone()
            return render_template_string('''
                <form method="POST">
                    Title: <input type="text" name="title" value="{{ post[0] }}"><br>
                    Content: <textarea name="content">{{ post[1] }}</textarea><br>
                    <input type="submit" value="Save">
                </form>
            ''', post=post)
    else:
        title = request.form['title']
        content = request.form['content']

        with connection.cursor() as cursor:
            cursor.execute("UPDATE boards SET title=%s, content=%s WHERE id=%s AND user_id=%s", (title, content, post_id, user_id))
            connection.commit()

        return redirect(url_for('index'))

@app.route('/board/delete/<post_id>', methods=['POST'])
def delete_post(post_id):
    user_id = session.get('user_id')
    if not user_id:
        return "Not logged in", 401

    with connection.cursor() as cursor:
        cursor.execute("UPDATE boards SET is_blocked=1 WHERE id=%s AND user_id=%s", (post_id, user_id))
        connection.commit()

    return redirect(url_for('index'))

@app.route('/board/<post_id>')
def view_post(post_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT title, content FROM boards WHERE id = %s", (post_id,))
        post = cursor.fetchone()
        if not post:
            return "Post not found", 404
        return render_template_string('''
            <h1>{{ post[0] }}</h1>
            <p>{{ post[1] }}</p>
        ''', post=post)

@app.route('/admin/block/<post_id>', methods=['POST'])
def block_post(post_id):
    user_id = session.get('user_id')
    if not user_id or not session.get('is_admin'):
        return "Not logged in or not an admin", 401

    with connection.cursor() as cursor:
        cursor.execute("UPDATE boards SET is_blocked=1 WHERE id=%s", (post_id,))
        connection.commit()

    return redirect(url_for('index'))

@app.route('/board/report/<post_id>', methods=['POST'])
def report_post(post_id):
    user_id = session.get('user_id')
    if not user_id:
        return "Not logged in", 401

    reason = request.form['reason']

    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO reports (post_id, user_id, reason) VALUES (%s, %s, %s)", (post_id, user_id, reason))
        connection.commit()

    return redirect(url_for('index'))

@app.route('/')
def index():
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, title, content FROM boards WHERE is_blocked=0")
        posts = cursor.fetchall()
    return render_template_string('''
        <h1>Community Board</h1>
        <form method="POST" action="/board">
            Title: <input type="text" name="title"><br>
            Content: <textarea name="content"></textarea><br>
            <input type="submit" value="Create Post">
        </form>
        {% for post in posts %}
            <h2><a href="/board/{{ post[0] }}">{{ post[1] }}</a></h2>
            <p>{{ post[2] }}</p>
        {% endfor %}
    ''', posts=posts)

if __name__ == '__main__':
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INT PRIMARY KEY AUTO_INCREMENT, username VARCHAR(50), is_admin BOOLEAN)")
        cursor.execute("CREATE TABLE IF NOT EXISTS boards (id INT PRIMARY KEY AUTO_INCREMENT, user_id INT, title VARCHAR(255), content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, is_blocked BOOLEAN DEFAULT FALSE, FOREIGN KEY (user_id) REFERENCES users(user_id))")
        cursor.execute("CREATE TABLE IF NOT EXISTS reports (report_id INT PRIMARY KEY AUTO_INCREMENT, post_id INT, user_id INT, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (post_id) REFERENCES boards(id), FOREIGN KEY (user_id) REFERENCES users(user_id))")
        cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
        cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
        cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (%s, %s, %s)", (1, 'First Post', 'This is the first post.'))
        cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (%s, %s, %s)", (2, 'Admin Post', 'This post was written by an admin.'))
        connection.commit()

    app.run(debug=True)