from flask import Flask, request, render_template_string, session, redirect, url_for, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database connection
def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize the database and insert dummy data
def init_db():
    with sqlite3.connect('mock_db.sqlite3') as connection:
        cursor = connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                is_deleted BOOLEAN DEFAULT 0
            )
        ''')
        cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES ('admin', 'admin@example.com', 'scrypt:32768:8:1$9M1Pw2z0KAwMnJqm$aefb7463fc2bbd6b92f9632f252ccaa8e9c1990a5f60e1ae37062c28f494545a60d92e6dd8c9194b8e6fb58a463af90340fc754048f87ac04dc77d03002bca2e', 1, 0)")
        cursor.execute("INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES ('user1', 'user1@example.com', 'scrypt:32768:8:1$AJjt3aJkFkvJ7lRt$84b281cf52f4f528236c5001e42f200874bd177d8ec1e80175c97aab0a106834779e21d7d5addb365a4f3065a30259dc25a6451b497b5034b11e4dba9e42982d', 0, 0)")
        connection.commit()

# Initialize the database
init_db()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password))
        conn.commit()
        conn.close()
        flash('User registered successfully')
        return redirect(url_for('login'))
    return render_template_string('''
        <form method="post">
            Username: <input type="text" name="username"><br>
            Email: <input type="email" name="email"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Register">
        </form>
    ''')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ? AND is_deleted = 0', (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Logged in successfully')
            return redirect(url_for('update'))
        else:
            flash('Invalid username or password')
    return render_template_string('''
        <form method="post">
            Username: <input type="text" name="username"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Login">
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
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET username = ?, email = ? WHERE id = ? AND is_deleted = 0', (username, email, session['user_id']))
        conn.commit()
        conn.close()
        flash('User information updated successfully')
        return redirect(url_for('update'))
    return render_template_string('''
        <form method="post">
            Username: <input type="text" name="username" value="{{ session['username'] }}"><br>
            Email: <input type="email" name="email" value="{{ session['username'] }}"><br>
            <input type="submit" value="Update">
        </form>
    ''')

@app.route('/delete', methods=['POST'])
def delete():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_deleted = 1 WHERE id = ? AND is_deleted = 0', (session['user_id'],))
    conn.commit()
    conn.close()
    session.pop('user_id')
    session.pop('username')
    flash('User account deleted successfully')
    return redirect(url_for('login'))

@app.route('/admin/delete_user', methods=['GET', 'POST'])
def admin_delete_user():
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('login'))
    if request.method == 'POST':
        user_id = request.form['user_id']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_deleted = 1 WHERE id = ? AND is_deleted = 0', (user_id,))
        conn.commit()
        conn.close()
        flash('User account deleted successfully')
        return redirect(url_for('admin_delete_user'))
    return render_template_string('''
        <form method="post">
            User ID: <input type="text" name="user_id"><br>
            <input type="submit" value="Delete User">
        </form>
    ''')

if __name__ == '__main__':
    app.run(debug=True)