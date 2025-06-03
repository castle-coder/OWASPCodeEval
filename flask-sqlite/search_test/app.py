from flask import Flask, request, render_template_string, session, redirect, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return redirect(url_for('search'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        keyword = request.form['keyword']
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        offset = (page - 1) * per_page
        conn = get_db_connection()
        if 'include_blocked' in request.form:
            cursor = conn.execute("SELECT id, user_id, title, substr(content, 1, 100) AS snippet, created_at FROM boards WHERE title LIKE ? OR content LIKE ? AND is_blocked = 1", ('%' + keyword + '%', '%' + keyword + '%'))
        else:
            cursor = conn.execute("SELECT id, user_id, title, substr(content, 1, 100) AS snippet, created_at FROM boards WHERE title LIKE ? OR content LIKE ?", ('%' + keyword + '%', '%' + keyword + '%'))
        posts = cursor.fetchall()
        total = cursor.rowcount
        conn.close()
        return render_template_string('''
            <form method="post">
                <input type="text" name="keyword" placeholder="Search..." required>
                <input type="checkbox" name="include_blocked"> Include Blocked
                <button type="submit">Search</button>
            </form>
            <ul>
                {% for post in posts %}
                    <li><a href="/board/{{ post['id'] }}">{{ post['title'] }} - {{ post['snippet'] }}</a></li>
                {% endfor %}
            </ul>
            {% if total > per_page %}
                <a href="?page={{ page - 1 if page > 1 else 1 }}&per_page={{ per_page }}">Previous</a>
                <a href="?page={{ page + 1 }}&per_page={{ per_page }}">Next</a>
            {% endif %}
        ''', posts=posts, total=total, per_page=per_page, page=page)

@app.route('/board/<int:post_id>')
def board(post_id):
    conn = get_db_connection()
    post = conn.execute("SELECT * FROM boards WHERE id = ?", (post_id,)).fetchone()
    conn.close()
    return render_template_string('''
        <h1>{{ post['title'] }}</h1>
        <p>{{ post['content'] }}</p>
        <p>Created at: {{ post['created_at'] }}</p>
    ''', post=post)

@app.route('/admin/search', methods=['GET', 'POST'])
def admin_search():
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('index'))
    if request.method == 'POST':
        keyword = request.form['keyword']
        include_blocked = 'include_blocked' in request.form
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        offset = (page - 1) * per_page
        conn = get_db_connection()
        if include_blocked:
            cursor = conn.execute("SELECT id, user_id, title, substr(content, 1, 100) AS snippet, created_at FROM boards WHERE title LIKE ? OR content LIKE ?", ('%' + keyword + '%', '%' + keyword + '%'))
        else:
            cursor = conn.execute("SELECT id, user_id, title, substr(content, 1, 100) AS snippet, created_at FROM boards WHERE title LIKE ? OR content LIKE ?", ('%' + keyword + '%', '%' + keyword + '%'))
        posts = cursor.fetchall()
        total = cursor.rowcount
        conn.close()
        return render_template_string('''
            <form method="post">
                <input type="text" name="keyword" placeholder="Search..." required>
                <input type="checkbox" name="include_blocked"> Include Blocked
                <button type="submit">Search</button>
            </form>
            <ul>
                {% for post in posts %}
                    <li><a href="/board/{{ post['id'] }}">{{ post['title'] }} - {{ post['snippet'] }}</a></li>
                {% endfor %}
            </ul>
            {% if total > per_page %}
                <a href="?page={{ page - 1 if page > 1 else 1 }}&per_page={{ per_page }}">Previous</a>
                <a href="?page={{ page + 1 }}&per_page={{ per_page }}">Next</a>
            {% endif %}
        ''', posts=posts, total=total, per_page=per_page, page=page)

if __name__ == '__main__':
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, is_admin BOOLEAN)")
    cursor.execute("CREATE TABLE IF NOT EXISTS boards (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_blocked BOOLEAN DEFAULT 0, FOREIGN KEY (user_id) REFERENCES users(user_id))")
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user1', 0)")
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)", (1, 'Search Demo', 'This content should be found when searching.'))
    conn.commit()
    conn.close()
    app.run(debug=True)