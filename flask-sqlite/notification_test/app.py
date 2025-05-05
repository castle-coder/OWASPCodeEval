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

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = False
    return redirect(url_for('notifications'))

@app.route('/notifications', methods=['GET', 'POST'])
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='1'))
    
    conn = get_db_connection()
    if request.method == 'POST':
        recipient_user_id = request.form['recipient_user_id']
        message = request.form['message']
        conn.execute('INSERT INTO notifications (recipient_user_id, sender_user_id, message) VALUES (?, ?, ?)',
                     (recipient_user_id, session['user_id'], message))
        conn.commit()
        conn.close()
        return redirect(url_for('notifications'))
    
    notifications = conn.execute('SELECT * FROM notifications WHERE recipient_user_id = ? AND is_blocked = 0', (session['user_id'],)).fetchall()
    conn.close()
    
    html = '''
    <form method="post">
        <input type="text" name="recipient_user_id" placeholder="Recipient User ID">
        <input type="text" name="message" placeholder="Message">
        <button type="submit">Send Notification</button>
    </form>
    <ul>
        {% for notification in notifications %}
        <li>
            {{ notification.message }} - {{ notification.created_at }} - {% if notification.is_read %}Read{% else %}Unread{% endif %}
            <form method="post" action="/notifications/read/{{ notification.id }}">
                <button type="submit">Mark as Read</button>
            </form>
            <form method="post" action="/notifications/delete/{{ notification.id }}">
                <button type="submit">Delete</button>
            </form>
        </li>
        {% endfor %}
    </ul>
    '''
    return render_template_string(html, notifications=notifications)

@app.route('/notifications/read/<notification_id>', methods=['POST'])
def mark_as_read(notification_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='1'))
    
    conn = get_db_connection()
    conn.execute('UPDATE notifications SET is_read = 1 WHERE id = ? AND recipient_user_id = ?', (notification_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('notifications'))

@app.route('/notifications/delete/<notification_id>', methods=['POST'])
def delete_notification(notification_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='1'))
    
    conn = get_db_connection()
    conn.execute('UPDATE notifications SET is_blocked = 1 WHERE id = ? AND recipient_user_id = ?', (notification_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('notifications'))

@app.route('/admin/block_notification/<notification_id>', methods=['POST'])
def block_notification(notification_id):
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('login', user_id='1'))
    
    conn = get_db_connection()
    conn.execute('UPDATE notifications SET is_blocked = 1 WHERE id = ?', (notification_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('notifications'))

@app.route('/notifications/report/<notification_id>', methods=['POST'])
def report_notification(notification_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='1'))
    
    reason = request.form['reason']
    conn = get_db_connection()
    conn.execute('INSERT INTO notification_reports (notification_id, user_id, reason) VALUES (?, ?, ?)',
                 (notification_id, session['user_id'], reason))
    conn.commit()
    conn.close()
    return redirect(url_for('notifications'))

if __name__ == '__main__':
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, is_admin BOOLEAN)')
    conn.execute('CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, recipient_user_id INTEGER, sender_user_id INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_read BOOLEAN DEFAULT 0, is_blocked BOOLEAN DEFAULT 0, FOREIGN KEY (recipient_user_id) REFERENCES users(user_id), FOREIGN KEY (sender_user_id) REFERENCES users(user_id))')
    conn.execute('CREATE TABLE IF NOT EXISTS notification_reports (report_id INTEGER PRIMARY KEY AUTOINCREMENT, notification_id INTEGER, user_id INTEGER, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (notification_id) REFERENCES notifications(id), FOREIGN KEY (user_id) REFERENCES users(user_id))')
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    conn.execute("INSERT INTO notifications (recipient_user_id, sender_user_id, message) VALUES (?, ?, ?)", (1, 2, 'System update'))
    conn.execute("INSERT INTO notifications (recipient_user_id, sender_user_id, message) VALUES (?, ?, ?)", (2, 1, 'Hello, admin!'))
    conn.commit()
    conn.close()
    app.run(debug=True)