from flask import Flask, request, render_template_string, redirect, url_for, session, jsonify
import sqlite3
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def create_tables():
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
    conn.execute('INSERT OR IGNORE INTO users (email, password, is_verified) VALUES (?, ?, ?)', ('test@example.com', 'hashed_pw', 0))
    conn.commit()
    conn.close()

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data['email']
    password = data['password']
    conn = get_db_connection()
    conn.execute('INSERT INTO users (email, password, is_verified) VALUES (?, ?, ?)', (email, password, False))
    conn.commit()
    conn.close()
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/send-verification/<int:user_id>', methods=['POST'])
def send_verification(user_id):
    conn = get_db_connection()
    token = secrets.token_urlsafe()
    expires_at = datetime.now() + timedelta(hours=1)
    conn.execute('INSERT INTO email_tokens (token, user_id, expires_at) VALUES (?, ?, ?)', (token, user_id, expires_at))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Verification token sent'}), 200

@app.route('/verify/<token>', methods=['GET'])
def verify(token):
    conn = get_db_connection()
    token_info = conn.execute('SELECT * FROM email_tokens WHERE token = ?', (token,)).fetchone()
    if token_info and token_info['expires_at'] > datetime.now():
        user_id = token_info['user_id']
        conn.execute('UPDATE users SET is_verified = ? WHERE id = ?', (True, user_id))
        conn.execute('DELETE FROM email_tokens WHERE token = ?', (token,))
        conn.commit()
        return jsonify({'message': 'Email verified successfully'}), 200
    else:
        return jsonify({'message': 'Invalid or expired token'}), 400

@app.route('/resend-verification/<int:user_id>', methods=['POST'])
def resend_verification(user_id):
    conn = get_db_connection()
    token = secrets.token_urlsafe()
    expires_at = datetime.now() + timedelta(hours=1)
    conn.execute('INSERT OR REPLACE INTO email_tokens (token, user_id, expires_at) VALUES (?, ?, ?)', (token, user_id, expires_at))
    conn.commit()
    conn.close()
    return jsonify({'message': 'New verification token sent'}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data['email']
    password = data['password']
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password)).fetchone()
    if user and user['is_verified']:
        session['user_id'] = user['id']
        session['is_verified'] = user['is_verified']
        return jsonify({'message': 'Login successful'}), 200
    else:
        return jsonify({'message': 'Invalid credentials or not verified'}), 401

@app.route('/profile', methods=['GET'])
def profile():
    if 'user_id' in session and session['is_verified']:
        user_id = session['user_id']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        return jsonify({'email': user['email'], 'is_verified': user['is_verified']}), 200
    else:
        return jsonify({'message': 'Unauthorized'}), 401

@app.route('/report', methods=['POST'])
def report():
    data = request.get_json()
    content = data['content']
    conn = get_db_connection()
    conn.execute('INSERT INTO reports (content) VALUES (?)', (content,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Report submitted successfully'}), 201

if __name__ == '__main__':
    app.run(debug=True)