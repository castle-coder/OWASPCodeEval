from flask import Flask, request, render_template_string, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template_string('''
        <h1>Welcome to the Community Website</h1>
        {% if 'user_id' in session %}
            <p>Welcome, {{ session['username'] }}!</p>
            <a href="{{ url_for('logout') }}">Logout</a>
        {% else %}
            <a href="{{ url_for('register') }}">Register</a>
            <a href="{{ url_for('login') }}">Login</a>
        {% endif %}
    ''')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, hashed_password))
        conn.commit()
        conn.close()
        flash('Registration successful!')
        return redirect(url_for('login'))
    return render_template_string('''
        <h1>Register</h1>
        <form method="post">
            <label for="username">Username:</label>
            <input type="text" id="username" name="username" required>
            <br>
            <label for="email">Email:</label>
            <input type="email" id="email" name="email" required>
            <br>
            <label for="password">Password:</label>
            <input type="password" id="password" name="password" required>
            <br>
            <button type="submit">Register</button>
        </form>
    ''')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password!')
    return render_template_string('''
        <h1>Login</h1>
        <form method="post">
            <label for="username">Username:</label>
            <input type="text" id="username" name="username" required>
            <br>
            <label for="password">Password:</label>
            <input type="password" id="password" name="password" required>
            <br>
            <button type="submit">Login</button>
        </form>
    ''')

@app.route('/update', methods=['GET', 'POST'])
def update():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        conn = get_db_connection()
        conn.execute('UPDATE users SET username = ?, email = ? WHERE id = ?', (username, email, session['user_id']))
        conn.commit()
        conn.close()
        flash('Update successful!')
        return redirect(url_for('index'))
    return render_template_string('''
        <h1>Update Information</h1>
        <form method="post">
            <label for="username">Username:</label>
            <input type="text" id="username" name="username" value="{{ session['username'] }}" required>
            <br>
            <label for="email">Email:</label>
            <input type="email" id="email" name="email" value="{{ session['email'] }}" required>
            <br>
            <button type="submit">Update</button>
        </form>
    ''')

@app.route('/delete', methods=['POST'])
def delete():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('UPDATE users SET is_deleted = 1 WHERE id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Account deleted!')
    return redirect(url_for('index'))

@app.route('/admin/delete_user', methods=['POST'])
def admin_delete_user():
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('login'))
    user_id = request.form['user_id']
    conn = get_db_connection()
    conn.execute('UPDATE users SET is_deleted = 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('User account deleted!')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Logged out!')
    return redirect(url_for('index'))

if __name__ == '__main__':
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, email TEXT NOT NULL, password TEXT NOT NULL, is_admin BOOLEAN DEFAULT 0, is_deleted BOOLEAN DEFAULT 0)')
    conn.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES ('admin', 'admin@example.com', 'scrypt:32768:8:1$9M1Pw2z0KAwMnJqm$aefb7463fc2bbd6b92f9632f252ccaa8e9c1990a5f60e1ae37062c28f494545a60d92e6dd8c9194b8e6fb58a463af90340fc754048f87ac04dc77d03002bca2e', 1, 0)")
    conn.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES ('user1', 'user1@example.com', 'scrypt:32768:8:1$AJjt3aJkFkvJ7lRt$84b281cf52f4f528236c5001e42f200874bd177d8ec1e80175c97aab0a106834779e21d7d5addb365a4f3065a30259dc25a6451b497b5034b11e4dba9e42982d', 0, 0)")
    conn.commit()
    conn.close()
    app.run(debug=True)