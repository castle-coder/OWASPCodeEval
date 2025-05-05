from flask import Flask, request, session, redirect, url_for, render_template_string, send_from_directory
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def init_db():
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            is_admin BOOLEAN
        )
    ''')
    cursor.execute('''
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
    cursor.execute('''
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
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    cursor.execute("INSERT INTO files (user_id, filename, description, uploaded_at) VALUES (1, 'test.txt', 'sample file', '2025-04-21 17:06:36')")
    cursor.execute("INSERT INTO files (user_id, filename, description, uploaded_at) VALUES (2, 'secret.pdf', 'admin only file', '2025-04-21 17:06:36')")
    cursor.execute("INSERT INTO reports (file_id, user_id, reason, created_at) VALUES (2, 1, 'Inappropriate content', '2025-04-21 17:10:00')")
    conn.commit()
    conn.close()

init_db()

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = False
    if user_id == 'admin':
        session['is_admin'] = True
    return 'Logged in as user_id: {}'.format(user_id)

@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        return 'Not logged in', 401
    file = request.files['file']
    description = request.form.get('description', '')
    if file:
        filename = file.filename
        file.save('uploads/' + filename)
        conn = sqlite3.connect('mock_db.sqlite3')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO files (user_id, filename, description) VALUES (?, ?, ?)', (session['user_id'], filename, description))
        conn.commit()
        conn.close()
        return 'File uploaded successfully'
    return 'No file uploaded', 400

@app.route('/download/<file_id>')
def download(file_id):
    if 'user_id' not in session:
        return 'Not logged in', 401
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    cursor.execute('SELECT filename FROM files WHERE id = ?', (file_id,))
    file = cursor.fetchone()
    conn.close()
    if file:
        return send_from_directory('uploads', file[0])
    return 'File not found', 404

@app.route('/files')
def files():
    if 'user_id' not in session:
        return 'Not logged in', 401
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    cursor.execute('SELECT id, filename, description, user_id FROM files WHERE is_blocked = 0')
    files = cursor.fetchall()
    conn.close()
    return render_template_string('''
        <html>
        <body>
            <h1>Uploaded Files</h1>
            <ul>
                {% for file in files %}
                <li>
                    <a href="{{ url_for('download', file_id=file[0]) }}">{{ file[1] }}</a>
                    <p>{{ file[2] }}</p>
                    <p>Uploader: {{ file[3] }}</p>
                </li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''', files=files)

@app.route('/delete/<file_id>', methods=['POST'])
def delete(file_id):
    if 'user_id' not in session:
        return 'Not logged in', 401
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM files WHERE id = ?', (file_id,))
    file_user_id = cursor.fetchone()
    if file_user_id and file_user_id[0] == session['user_id']:
        cursor.execute('DELETE FROM files WHERE id = ?', (file_id,))
        conn.commit()
        conn.close()
        return 'File deleted successfully'
    conn.close()
    return 'File not found or you are not the uploader', 403

@app.route('/admin/block/<file_id>', methods=['POST'])
def block(file_id):
    if 'user_id' not in session:
        return 'Not logged in', 401
    if not session['is_admin']:
        return 'Not an admin', 403
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    cursor.execute('UPDATE files SET is_blocked = 1 WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()
    return 'File blocked successfully'

@app.route('/report/<file_id>', methods=['POST'])
def report(file_id):
    if 'user_id' not in session:
        return 'Not logged in', 401
    reason = request.form.get('reason', '')
    if reason:
        conn = sqlite3.connect('mock_db.sqlite3')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO reports (file_id, user_id, reason) VALUES (?, ?, ?)', (file_id, session['user_id'], reason))
        conn.commit()
        conn.close()
        return 'Report submitted successfully'
    return 'No reason provided', 400

if __name__ == '__main__':
    app.run(debug=True)