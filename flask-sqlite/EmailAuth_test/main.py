from flask import Flask, request, redirect, url_for, session, render_template_string
import sqlite3
import hashlib
import random
import string
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database connection
def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database and insert test users
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password_hash TEXT,
            is_verified BOOLEAN DEFAULT 0,
            verification_token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    # Insert test users
    conn.execute('''
        INSERT OR IGNORE INTO users (email, password_hash, is_verified, verification_token) VALUES (?, ?, ?, ?)
    ''', ('test1@example.com', hashlib.sha256('password1'.encode()).hexdigest(), 1, None))
    conn.execute('''
        INSERT OR IGNORE INTO users (email, password_hash, is_verified, verification_token) VALUES (?, ?, ?, ?)
    ''', ('test2@example.com', hashlib.sha256('password2'.encode()).hexdigest(), 0, None))
    conn.commit()

init_db()

# Generate a random token
def generate_token(length=32):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Register a new user
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        verification_token = generate_token()

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO users (email, password_hash, verification_token) VALUES (?, ?, ?)
        ''', (email, password_hash, verification_token))
        conn.commit()
        conn.close()

        # Simulate sending email
        print(f"Verification email sent to {email} with token: {verification_token}")
        return redirect(url_for('verify', token=verification_token))
    return render_template_string('''
        <form method="post">
            Email: <input type="email" name="email" required><br>
            Password: <input type="password" name="password" required><br>
            <input type="submit" value="Register">
        </form>
    ''')

# Verify user email
@app.route('/verify/<token>', methods=['GET'])
def verify(token):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE verification_token = ?', (token,)).fetchone()
    conn.close()

    if user:
        conn = get_db_connection()
        conn.execute('''
            UPDATE users SET is_verified = 1, verification_token = NULL WHERE user_id = ?
        ''', (user['user_id'],))
        conn.commit()
        conn.close()
        return 'Email verified successfully!'
    return 'Invalid or expired token.'

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND password_hash = ? AND is_verified = 1', (email, password_hash)).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['user_id']
            session['email'] = user['email']
            return 'Logged in successfully!'
        return 'Login failed. Please check your credentials.'
    return render_template_string('''
        <form method="post">
            Email: <input type="email" name="email" required><br>
            Password: <input type="password" name="password" required><br>
            <input type="submit" value="Login">
        </form>
    ''')

# Resend verification email
@app.route('/resend', methods=['GET', 'POST'])
def resend():
    if request.method == 'POST':
        email = request.form['email']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND is_verified = 0', (email,)).fetchone()
        conn.close()

        if user:
            verification_token = generate_token()
            conn = get_db_connection()
            conn.execute('''
                UPDATE users SET verification_token = ? WHERE user_id = ?
            ''', (verification_token, user['user_id']))
            conn.commit()
            conn.close()

            # Simulate sending email
            print(f"Verification email resent to {email} with token: {verification_token}")
            return 'Verification email resent successfully!'
        return 'Email not found or already verified.'
    return render_template_string('''
        <form method="post">
            Email: <input type="email" name="email" required><br>
            <input type="submit" value="Resend Verification Email">
        </form>
    ''')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return 'Logged out successfully!'

if __name__ == '__main__':
    app.run(debug=True)