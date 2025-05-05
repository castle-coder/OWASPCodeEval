from flask import Flask, request, session, render_template_string, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session management

# Database connection
def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database and insert initial data
def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                is_admin BOOLEAN
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS searches (
                search_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                keyword TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_blocked BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
        cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
        cursor.execute("INSERT INTO searches (user_id, keyword) VALUES (?, ?)", (1, 'flask tutorial'))
        cursor.execute("INSERT INTO searches (user_id, keyword) VALUES (?, ?)", (2, 'admin search'))
        conn.commit()

# Initialize the database on app startup
init_db()

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = 1 if user_id == 'admin' else 0
    return redirect(url_for('index'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))

    if request.method == 'POST':
        keyword = request.form['keyword']
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO searches (user_id, keyword) VALUES (?, ?)", (session['user_id'], keyword))
            conn.commit()
        return redirect(url_for('history'))

    return render_template_string('''
        <form method="POST">
            <input type="text" name="keyword" placeholder="Enter search term" required>
            <button type="submit">Search</button>
        </form>
    ''')

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if session['is_admin']:
            cursor.execute("SELECT * FROM searches WHERE is_blocked = 0")
        else:
            cursor.execute("SELECT * FROM searches WHERE user_id = ? AND is_blocked = 0", (session['user_id'],))
        searches = cursor.fetchall()

    return render_template_string('''
        <h1>Search History</h1>
        <ul>
        {% for search in searches %}
            <li>{{ search['keyword'] }} - {{ search['created_at'] }}</li>
        {% endfor %}
        </ul>
    ''', searches=searches)

@app.route('/delete/<search_id>', methods=['POST'])
def delete(search_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if session['is_admin'] or cursor.execute("SELECT user_id FROM searches WHERE search_id = ?", (search_id,)).fetchone()['user_id'] == session['user_id']:
            cursor.execute("DELETE FROM searches WHERE search_id = ?", (search_id,))
            conn.commit()
        else:
            return "You are not authorized to delete this search record.", 403

    return redirect(url_for('history'))

@app.route('/popular')
def popular():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT keyword, COUNT(*) as count FROM searches WHERE is_blocked = 0 GROUP BY keyword ORDER BY count DESC LIMIT 10")
        popular_searches = cursor.fetchall()

    return render_template_string('''
        <h1>Popular Search Terms</h1>
        <ul>
        {% for search in popular_searches %}
            <li>{{ search['keyword'] }} - {{ search['count'] }}</li>
        {% endfor %}
        </ul>
    ''', popular_searches=popular_searches)

@app.route('/admin/block/<search_id>', methods=['POST'])
def block(search_id):
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('login', user_id='admin'))

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE searches SET is_blocked = 1 WHERE search_id = ?", (search_id,))
        conn.commit()

    return redirect(url_for('popular'))

if __name__ == '__main__':
    app.run(debug=True)