from flask import Flask, request, session, redirect, url_for, render_template_string
import sqlite3
import hashlib

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/login/<member_id>', methods=['GET'])
def login(member_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE user_id = ? AND is_deleted = 0', (member_id,)).fetchone()
    conn.close()
    if user:
        session['member_id'] = user['user_id']
        session['is_admin'] = user['is_admin']
        return redirect(url_for('index'))
    return 'Login failed', 401

@app.route('/members/register', methods=['POST'])
def register():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db_connection()
    conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, hashed_password))
    conn.commit()
    conn.close()
    return 'Registration successful', 201

@app.route('/members/<member_id>', methods=['GET'])
def view_member(member_id):
    if 'member_id' not in session:
        return 'Not logged in', 401
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE user_id = ? AND is_deleted = 0', (member_id,)).fetchone()
    conn.close()
    if user:
        return render_template_string('<h1>Member Profile</h1><p>Username: {{ user.username }}</p><p>Email: {{ user.email }}</p>', user=user)
    return 'Member not found', 404

@app.route('/members/update', methods=['POST'])
def update_member():
    if 'member_id' not in session:
        return 'Not logged in', 401
    member_id = session['member_id']
    username = request.form['username']
    email = request.form['email']
    conn = get_db_connection()
    conn.execute('UPDATE users SET username = ?, email = ? WHERE user_id = ?', (username, email, member_id))
    conn.commit()
    conn.close()
    return 'Profile updated', 200

@app.route('/members/delete', methods=['POST'])
def delete_member():
    if 'member_id' not in session:
        return 'Not logged in', 401
    member_id = session['member_id']
    conn = get_db_connection()
    conn.execute('UPDATE users SET is_deleted = 1 WHERE user_id = ?', (member_id,))
    conn.commit()
    conn.close()
    return 'Account deleted', 200

@app.route('/admin/deactivate_member/<member_id>', methods=['POST'])
def deactivate_member(member_id):
    if 'member_id' not in session or not session['is_admin']:
        return 'Not authorized', 403
    conn = get_db_connection()
    conn.execute('UPDATE users SET is_deleted = 1 WHERE user_id = ?', (member_id,))
    conn.commit()
    conn.close()
    return 'Member deactivated', 200

@app.route('/members', methods=['GET'])
def list_members():
    if 'member_id' not in session:
        return 'Not logged in', 401
    conn = get_db_connection()
    members = conn.execute('SELECT * FROM users WHERE is_deleted = 0').fetchall()
    conn.close()
    return render_template_string('<h1>Active Members</h1><ul>{% for member in members %}<li>{{ member.username }} ({{ member.email }})</li>{% endfor %}</ul>', members=members)

if __name__ == '__main__':
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, email TEXT NOT NULL, password TEXT NOT NULL, is_admin BOOLEAN DEFAULT 0, is_deleted BOOLEAN DEFAULT 0)')
    hashed_password = hashlib.sha256('user'.encode()).hexdigest()
    conn.execute('INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)', ('user', 'user@example.com', hashed_password, 0, 0))
    hashed_password = hashlib.sha256('admin'.encode()).hexdigest()
    conn.execute('INSERT INTO users (username, email, password, is_admin, is_deleted) VALUES (?, ?, ?, ?, ?)', ('admin', 'admin@example.com', hashed_password, 1, 0))
    conn.commit()
    conn.close()
    app.run(debug=True)