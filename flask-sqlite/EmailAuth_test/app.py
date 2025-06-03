import sqlite3
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            is_verified BOOLEAN
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS email_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT
        )
    ''')
    conn.execute("INSERT OR IGNORE INTO users (email, password, is_verified) VALUES ('test@example.com', 'hashed_pw', 0)")
    conn.commit()
    conn.close()

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute('INSERT INTO users (email, password, is_verified) VALUES (?, ?, ?)', (data['email'], data['password'], False))
    conn.commit()
    conn.close()
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/send-verification/<int:user_id>', methods=['POST'])
def send_verification(user_id):
    token = secrets.token_hex(16)
    expires_at = datetime.now() + timedelta(hours=1)
    conn = get_db_connection()
    conn.execute('INSERT INTO email_tokens (token, user_id, expires_at) VALUES (?, ?, ?)', (token, user_id, expires_at))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Verification email sent', 'token': token}), 200

@app.route('/verify/<string:token>', methods=['GET'])
def verify(token):
    conn = get_db_connection()
    token_info = conn.execute('SELECT * FROM email_tokens WHERE token = ?', (token,)).fetchone()
    if token_info and datetime.now() < token_info['expires_at']:
        conn.execute('UPDATE users SET is_verified = ? WHERE id = ?', (True, token_info['user_id']))
        conn.execute('DELETE FROM email_tokens WHERE token = ?', (token,))
        conn.commit()
        return jsonify({'message': 'Email verified successfully'}), 200
    else:
        return jsonify({'message': 'Invalid or expired token'}), 400

@app.route('/resend-verification/<int:user_id>', methods=['POST'])
def resend_verification(user_id):
    return send_verification(user_id)

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ? AND is_verified = ?', (data['email'], data['password'], True)).fetchone()
    conn.close()
    if user:
        session['user_id'] = user['id']
        session['is_verified'] = user['is_verified']
        return jsonify({'message': 'Login successful'}), 200
    else:
        return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/profile', methods=['GET'])
def profile():
    if 'user_id' in session and session['is_verified']:
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
        return jsonify({'email': user['email'], 'is_verified': user['is_verified']})
    else:
        return jsonify({'message': 'Unauthorized'}), 401

@app.route('/report', methods=['POST'])
def report():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute('INSERT INTO reports (content) VALUES (?)', (data['content'],))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Report submitted successfully'}), 201

if __name__ == '__main__':
    init_db()
    app.run(debug=True)