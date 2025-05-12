from flask import Flask, request, render_template_string, session, redirect, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/search', methods=['GET'])
def search():
    return render_template_string('''
        <form method="post">
            <input type="text" name="keyword" placeholder="Search..." required>
            <button type="submit">Search</button>
        </form>
    ''')

@app.route('/search', methods=['POST'])
def execute_search():
    keyword = request.form['keyword']
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT id, user_id, title, SUBSTR(content, 1, 100) AS snippet, created_at FROM boards WHERE title LIKE ? OR content LIKE ? LIMIT ? OFFSET ?"
    cursor.execute(query, ('%' + keyword + '%', '%' + keyword + '%', per_page, offset))
    posts = cursor.fetchall()
    conn.close()

    prev_page = page - 1 if page > 1 else None
    next_page = page + 1

    return render_template_string('''
        <ul>
            {% for post in posts %}
                <li><a href="/board/{{ post.id }}">{{ post.title }} - {{ post.snippet }}</a></li>
            {% endfor %}
        </ul>
        {% if prev_page %}
            <a href="?page={{ prev_page }}">Previous</a>
        {% endif %}
        {% if next_page %}
            <a href="?page={{ next_page }}">Next</a>
        {% endif %}
    ''', posts=posts)

@app.route('/admin/search', methods=['GET'])
def admin_search():
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('search'))
    return render_template_string('''
        <form method="post">
            <input type="text" name="keyword" placeholder="Search..." required>
            <input type="checkbox" name="include_blocked"> Include Blocked Posts
            <button type="submit">Search</button>
        </form>
    ''')

@app.route('/admin/search', methods=['POST'])
def execute_admin_search():
    keyword = request.form['keyword']
    include_blocked = 'include_blocked' in request.form
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT id, user_id, title, SUBSTR(content, 1, 100) AS snippet, created_at FROM boards WHERE title LIKE ? OR content LIKE ?"
    if include_blocked:
        query += " OR is_blocked = 1"
    query += " LIMIT ? OFFSET ?"
    cursor.execute(query, ('%' + keyword + '%', '%' + keyword + '%', per_page, offset))
    posts = cursor.fetchall()
    conn.close()

    prev_page = page - 1 if page > 1 else None
    next_page = page + 1

    return render_template_string('''
        <ul>
            {% for post in posts %}
                <li><a href="/board/{{ post.id }}">{{ post.title }} - {{ post.snippet }}</a></li>
            {% endfor %}
        </ul>
        {% if prev_page %}
            <a href="?page={{ prev_page }}">Previous</a>
        {% endif %}
        {% if next_page %}
            <a href="?page={{ next_page }}">Next</a>
        {% endif %}
    ''', posts=posts)

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