from flask import Flask, request, session, render_template_string, redirect, url_for
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
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    cursor.execute("INSERT INTO chats (user_id, content) VALUES (?, ?)", (1, 'Hello, world!'))
    cursor.execute("INSERT INTO chats (user_id, content) VALUES (?, ?)", (2, 'Admin announcement'))
    conn.commit()
    conn.close()

init_db()

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = 1 if user_id == 'admin' else 0
    return redirect(url_for('chats'))

@app.route('/chats', methods=['GET', 'POST'])
def chats():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    if request.method == 'POST':
        content = request.form['content']
        conn = sqlite3.connect('mock_db.sqlite3')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chats (user_id, content) VALUES (?, ?)", (session['user_id'], content))
        conn.commit()
        conn.close()
    
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chats")
    chats = cursor.fetchall()
    conn.close()
    
    return render_template_string('''
        <h1>Chat</h1>
        <form method="POST">
            <input type="text" name="content" required>
            <button type="submit">Send</button>
        </form>
        <ul>
            {% for chat in chats %}
            <li>{{ chat[2] }} - {{ chat[3].strftime('%Y-%m-%d %H:%M:%S') }} - {{ chat[1] }}</li>
            {% endfor %}
        </ul>
    ''', chats=chats)

@app.route('/chats/edit/<chat_id>', methods=['GET', 'POST'])
def edit_chat(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    if request.method == 'POST':
        new_content = request.form['content']
        conn = sqlite3.connect('mock_db.sqlite3')
        cursor = conn.cursor()
        cursor.execute("UPDATE chats SET content = ? WHERE id = ?", (new_content, chat_id))
        conn.commit()
        conn.close()
        return redirect(url_for('chats'))
    
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
    chat = cursor.fetchone()
    conn.close()
    
    return render_template_string('''
        <h1>Edit Chat</h1>
        <form method="POST">
            <input type="text" name="content" value="{{ chat[2] }}" required>
            <button type="submit">Save</button>
        </form>
    ''', chat=chat)

@app.route('/chats/delete/<chat_id>', methods=['POST'])
def delete_chat(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    cursor.execute("UPDATE chats SET is_blocked = 1 WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('chats'))

@app.route('/admin/block/<chat_id>', methods=['POST'])
def block_chat(chat_id):
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('login', user_id='admin'))
    
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    cursor.execute("UPDATE chats SET is_blocked = 1 WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('chats'))

@app.route('/chats/report/<chat_id>', methods=['POST'])
def report_chat(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    reason = request.form['reason']
    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_reports (chat_id, user_id, reason) VALUES (?, ?, ?)", (chat_id, session['user_id'], reason))
    conn.commit()
    conn.close()
    
    return redirect(url_for('chats'))

if __name__ == '__main__':
    app.run(debug=True)