from flask import Flask, request, session, redirect, url_for, render_template_string
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
    return redirect(url_for('files'))

@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    file = request.files['file']
    description = request.form['description']
    if file.filename == '':
        return 'No selected file'
    if file:
        filename = file.filename
        file.save(f'uploads/{filename}')
        conn = get_db_connection()
        conn.execute('INSERT INTO files (user_id, filename, description) VALUES (?, ?, ?)',
                     (session['user_id'], filename, description))
        conn.commit()
        conn.close()
        return redirect(url_for('files'))

@app.route('/download/<file_id>')
def download(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    conn = get_db_connection()
    file = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
    if file and not file['is_blocked']:
        return send_from_directory('uploads', file['filename'])
    conn.close()
    return 'File not found or blocked', 404

@app.route('/files')
def files():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    conn = get_db_connection()
    files = conn.execute('SELECT * FROM files WHERE is_blocked = 0').fetchall()
    conn.close()
    return render_template_string('''
        <h1>Files</h1>
        <ul>
            {% for file in files %}
                <li>{{ file.filename }} - {{ file.description }} - Uploaded by {{ file.user_id }} - <a href="{{ url_for('download', file_id=file.id) }}">Download</a></li>
            {% endfor %}
        </ul>
    ''', files=files)

@app.route('/delete/<file_id>', methods=['POST'])
def delete(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    conn = get_db_connection()
    file = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
    if file and file['user_id'] == session['user_id']:
        conn.execute('DELETE FROM files WHERE id = ?', (file_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('files'))
    conn.close()
    return 'File not found or not yours', 404

@app.route('/admin/block/<file_id>', methods=['POST'])
def block(file_id):
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('login', user_id='user'))
    conn = get_db_connection()
    conn.execute('UPDATE files SET is_blocked = 1 WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('files'))

@app.route('/report/<file_id>', methods=['POST'])
def report(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    reason = request.form['reason']
    conn = get_db_connection()
    conn.execute('INSERT INTO reports (file_id, user_id, reason) VALUES (?, ?, ?)',
                 (file_id, session['user_id'], reason))
    conn.commit()
    conn.close()
    return redirect(url_for('files'))

if __name__ == '__main__':
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, is_admin BOOLEAN)')
    conn.execute('CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT, description TEXT, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_blocked BOOLEAN DEFAULT 0, FOREIGN KEY (user_id) REFERENCES users(user_id))')
    conn.execute('CREATE TABLE IF NOT EXISTS reports (report_id INTEGER PRIMARY KEY AUTOINCREMENT, file_id INTEGER, user_id INTEGER, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (file_id) REFERENCES files(id), FOREIGN KEY (user_id) REFERENCES users(user_id))')
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    conn.commit()
    conn.close()
    app.run(debug=True)