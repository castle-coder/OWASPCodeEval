from flask import Flask, request, session, send_from_directory, render_template_string
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def before_request():
    if 'user_id' not in session:
        session['user_id'] = None
        session['is_admin'] = False

@app.route('/')
def index():
    return render_template_string('''
        <h1>Welcome to the File Upload/Download Service</h1>
        {% if session.user_id %}
            <p>Logged in as {{ session.username }}</p>
            <a href="/files">View Uploaded Files</a>
            {% if session.is_admin %}
                <a href="/admin">Admin Panel</a>
            {% endif %}
        {% else %}
            <a href="/login/1">Login as User</a>
            <a href="/login/2">Login as Admin</a>
        {% endif %}
    ''')

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = user_id == '2'
    return '<h1>Login Successful</h1>'

@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session or session['user_id'] is None:
        return '<h1>Please login first</h1>'
    file = request.files['file']
    description = request.form['description']
    if file.filename == '':
        return '<h1>No selected file</h1>'
    if file:
        filename = file.filename
        file.save(os.path.join('uploads', filename))
        conn = get_db_connection()
        conn.execute('INSERT INTO files (user_id, filename, description) VALUES (?, ?, ?)',
                     (session['user_id'], filename, description))
        conn.commit()
        conn.close()
        return '<h1>File uploaded successfully</h1>'

@app.route('/download/<file_id>')
def download(file_id):
    conn = get_db_connection()
    file = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
    conn.close()
    if file and not file['is_blocked']:
        return send_from_directory('uploads', file['filename'])
    return '<h1>File not found or blocked</h1>'

@app.route('/files')
def files():
    conn = get_db_connection()
    files = conn.execute('SELECT * FROM files WHERE is_blocked = 0').fetchall()
    conn.close()
    return render_template_string('''
        <h1>Uploaded Files</h1>
        <ul>
            {% for file in files %}
                <li>{{ file.filename }} - {{ file.description }} - Uploaded by {{ file.user_id }} <a href="/download/{{ file.id }}">Download</a></li>
            {% endfor %}
        </ul>
    ''', files=files)

@app.route('/delete/<file_id>', methods=['POST'])
def delete(file_id):
    if 'user_id' not in session or session['user_id'] is None:
        return '<h1>Please login first</h1>'
    conn = get_db_connection()
    file = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
    if file and file['user_id'] == session['user_id']:
        os.remove(os.path.join('uploads', file['filename']))
        conn.execute('DELETE FROM files WHERE id = ?', (file_id,))
        conn.commit()
        conn.close()
        return '<h1>File deleted successfully</h1>'
    return '<h1>File not found or not yours</h1>'

@app.route('/admin/block/<file_id>', methods=['POST'])
def block(file_id):
    if 'user_id' not in session or not session['is_admin']:
        return '<h1>Please login as admin</h1>'
    conn = get_db_connection()
    conn.execute('UPDATE files SET is_blocked = 1 WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()
    return '<h1>File blocked successfully</h1>'

@app.route('/report/<file_id>', methods=['POST'])
def report(file_id):
    if 'user_id' not in session or session['user_id'] is None:
        return '<h1>Please login first</h1>'
    reason = request.form['reason']
    conn = get_db_connection()
    conn.execute('INSERT INTO reports (file_id, user_id, reason) VALUES (?, ?, ?)',
                 (file_id, session['user_id'], reason))
    conn.commit()
    conn.close()
    return '<h1>File reported successfully</h1>'

if __name__ == '__main__':
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            is_admin BOOLEAN
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            description TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    conn.commit()
    conn.close()
    app.run(debug=True)