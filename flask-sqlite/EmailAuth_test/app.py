from flask import Flask, request, render_template_string, redirect, url_for, session, flash
import sqlite3
import os
import secrets
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATABASE = 'mock_db.sqlite3'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def before_request():
    if 'user_id' in session:
        g.user = get_db_connection().execute('SELECT * FROM users WHERE user_id = ?', (session['user_id'],)).fetchone()
    else:
        g.user = None

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        if conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone() is not None:
            flash('Email already registered.')
        else:
            password_hash = generate_password_hash(password)
            token = secrets.token_urlsafe()
            conn.execute('INSERT INTO users (email, password_hash, verification_token) VALUES (?, ?, ?)', (email, password_hash, token))
            conn.commit()
            print(f"Verification link: {url_for('verify', token=token, _external=True)}")
            flash('Registration successful. Please check your email for verification.')
        conn.close()
        return redirect(url_for('register'))
    return render_template_string('''
        <form method="post">
            Email: <input type="email" name="email"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Register">
        </form>
    ''')

@app.route('/verify/<token>', methods=['GET'])
def verify(token):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE verification_token = ?', (token,)).fetchone()
    if user is not None:
        conn.execute('UPDATE users SET is_verified = 1, verification_token = NULL WHERE user_id = ?', (user['user_id'],))
        conn.commit()
        flash('Email verified successfully.')
    else:
        flash('Invalid verification token.')
    conn.close()
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user is not None and check_password_hash(user['password_hash'], password) and user['is_verified']:
            session['user_id'] = user['user_id']
            session['email'] = user['email']
            flash('Login successful.')
        else:
            flash('Invalid email, password, or not verified.')
        conn.close()
        return redirect(url_for('login'))
    return render_template_string('''
        <form method="post">
            Email: <input type="email" name="email"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Login">
        </form>
    ''')

@app.route('/resend', methods=['GET', 'POST'])
def resend():
    if request.method == 'POST':
        email = request.form['email']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND is_verified = 0', (email,)).fetchone()
        if user is not None:
            token = secrets.token_urlsafe()
            conn.execute('UPDATE users SET verification_token = ? WHERE user_id = ?', (token, user['user_id']))
            conn.commit()
            print(f"Verification link: {url_for('verify', token=token, _external=True)}")
            flash('Verification email resent.')
        else:
            flash('Email not found or already verified.')
        conn.close()
        return redirect(url_for('resend'))
    return render_template_string('''
        <form method="post">
            Email: <input type="email" name="email"><br>
            <input type="submit" value="Resend Verification Email">
        </form>
    ''')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('login'))

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
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
        conn.execute('''
            INSERT INTO users (email, password_hash, is_verified) VALUES (?, ?, 1)
        ''', ('admin@example.com', generate_password_hash('admin123'), True))
        conn.execute('''
            INSERT INTO users (email, password_hash, verification_token)
        ''', ('user@example.com', generate_password_hash('user123'), secrets.token_urlsafe()))
        conn.commit()
        conn.close()
    app.run(debug=True)