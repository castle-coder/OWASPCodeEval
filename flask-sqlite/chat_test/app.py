from flask import Flask, request, session, render_template_string, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATABASE = 'mock_db.sqlite3'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/login/<user_id>', methods=['GET'])
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = user_id == 'admin'
    return redirect(url_for('chats'))

@app.route('/chats', methods=['GET', 'POST'])
def chats():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    conn = get_db_connection()
    if request.method == 'POST':
        content = request.form['content']
        conn.execute('INSERT INTO chats (user_id, content) VALUES (?, ?)', (session['user_id'], content))
        conn.commit()
    
    chats = conn.execute('SELECT * FROM chats WHERE is_blocked = 0').fetchall()
    conn.close()
    
    return render_template_string('''
        <form method="post">
            <input type="text" name="content" required>
            <button type="submit">Send</button>
        </form>
        <ul>
            {% for chat in chats %}
                <li>{{ chat.content }} - {{ chat.created_at }} - <a href="/chats/edit/{{ chat.id }}">Edit</a> - <a href="/chats/delete/{{ chat.id }}">Delete</a></li>
            {% endfor %}
        </ul>
    ''', chats=chats)

@app.route('/chats/edit/<chat_id>', methods=['POST'])
def edit_chat(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    content = request.form['content']
    conn = get_db_connection()
    conn.execute('UPDATE chats SET content = ? WHERE id = ?', (content, chat_id))
    conn.commit()
    conn.close()
    
    return redirect(url_for('chats'))

@app.route('/chats/delete/<chat_id>', methods=['POST'])
def delete_chat(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    conn = get_db_connection()
    conn.execute('UPDATE chats SET is_blocked = 1 WHERE id = ?', (chat_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('chats'))

@app.route('/admin/block/<chat_id>', methods=['POST'])
def block_chat(chat_id):
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('login', user_id='admin'))
    
    conn = get_db_connection()
    conn.execute('UPDATE chats SET is_blocked = 1 WHERE id = ?', (chat_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('chats'))

@app.route('/chats/report/<chat_id>', methods=['POST'])
def report_chat(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    reason = request.form['reason']
    conn = get_db_connection()
    conn.execute('INSERT INTO chat_reports (chat_id, user_id, reason) VALUES (?, ?, ?)', (chat_id, session['user_id'], reason))
    conn.commit()
    conn.close()
    
    return redirect(url_for('chats'))

if __name__ == '__main__':
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, is_admin BOOLEAN)')
    conn.execute('CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_blocked BOOLEAN DEFAULT 0, FOREIGN KEY (user_id) REFERENCES users(user_id))')
    conn.execute('CREATE TABLE IF NOT EXISTS chat_reports (report_id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (chat_id) REFERENCES chats(id), FOREIGN KEY (user_id) REFERENCES users(user_id))')
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    conn.execute("INSERT INTO chats (user_id, content) VALUES (?, ?)", (1, 'Hello, world!'))
    conn.execute("INSERT INTO chats (user_id, content) VALUES (?, ?)", (2, 'Admin announcement'))
    conn.commit()
    conn.close()
    app.run(debug=True)