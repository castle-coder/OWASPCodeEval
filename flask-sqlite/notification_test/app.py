from flask import Flask, request, session, render_template_string, redirect, url_for, abort
import sqlite3
import re
import html

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = 'mock_db.sqlite3'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.errorhandler(500)
def internal_error(e):
    return "Internal Server Error", 500

@app.route('/login/<user_id>')
def login(user_id):
    session.clear()
    # SQL injection pattern detection
    if re.search(r"(\'|--|;|\bOR\b|\bAND\b)", user_id, re.IGNORECASE):
        return redirect(url_for('notifications'))
    # convert to int (abc will raise ValueError -> 500)
    uid = int(user_id)
    session['user_id'] = uid
    conn = get_db()
    row = conn.execute('SELECT is_admin FROM users WHERE user_id = ?', (uid,)).fetchone()
    conn.close()
    session['is_admin'] = bool(row['is_admin']) if row else False
    return redirect(url_for('notifications'))

@app.route('/notifications', methods=['GET', 'POST'])
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='1'))
    user_id = session['user_id']
    conn = get_db()
    if request.method == 'POST':
        rid = request.form.get('recipient_user_id')
        msg = request.form.get('message')
        if not rid or not msg:
            abort(400)
        conn.execute(
            'INSERT INTO notifications (recipient_user_id, sender_user_id, message) VALUES (?,?,?)',
            (int(rid), user_id, msg)
        )
        conn.commit()
    notes = conn.execute(
        'SELECT * FROM notifications WHERE recipient_user_id = ? AND is_blocked = 0',
        (user_id,)
    ).fetchall()
    reports = conn.execute(
        'SELECT * FROM notification_reports WHERE user_id = ?',
        (user_id,)
    ).fetchall()
    conn.close()
    template = '''
    <h1>Notifications</h1>
    <form method="post">
      To User ID: <input name="recipient_user_id"><br>
      Message: <input name="message"><br>
      <button>Send</button>
    </form>
    <h2>Your Notifications</h2>
    <ul>
      {% for n in notes %}
        <li>
          {{ n.created_at }} - From {{ n.sender_user_id }}: {{ n.message|e }}
          {% if not n.is_read %}
            <form method="post" action="{{ url_for('mark_read',notification_id=n.id) }}"><button>Mark Read</button></form>
          {% endif %}
          <form method="post" action="{{ url_for('delete_notification',notification_id=n.id) }}"><button>Delete</button></form>
        </li>
      {% endfor %}
    </ul>
    <h2>Your Reports</h2>
    <ul>
      {% for r in reports %}
        <li>Notification {{ r.notification_id }} reported: {{ r.reason|e }}</li>
      {% endfor %}
    </ul>
    '''
    return render_template_string(template, notes=notes, reports=reports)

@app.route('/notifications/read/<int:notification_id>', methods=['POST'])
def mark_read(notification_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='1'))
    conn = get_db()
    conn.execute(
        'UPDATE notifications SET is_read=1 WHERE id=? AND recipient_user_id=?',
        (notification_id, session['user_id'])
    )
    conn.commit()
    conn.close()
    return redirect(url_for('notifications'))

@app.route('/notifications/delete/<int:notification_id>', methods=['POST'])
def delete_notification(notification_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='1'))
    conn = get_db()
    conn.execute(
        'UPDATE notifications SET is_blocked=1 WHERE id=? AND recipient_user_id=?',
        (notification_id, session['user_id'])
    )
    conn.commit()
    conn.close()
    return redirect(url_for('notifications'))

@app.route('/admin/block_notification/<int:notification_id>', methods=['POST'])
def admin_block(notification_id):
    if 'user_id' not in session or not session.get('is_admin'):
        abort(403)
    conn = get_db()
    conn.execute(
        'UPDATE notifications SET is_blocked=1 WHERE id=?',
        (notification_id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('notifications'))

@app.route('/notifications/report/<int:notification_id>', methods=['POST'])
def report_notification(notification_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='1'))
    reason = request.form.get('reason', '')
    safe_reason = html.escape(reason)
    conn = get_db()
    conn.execute(
        'INSERT INTO notification_reports (notification_id, user_id, reason) VALUES (?,?,?)',
        (notification_id, session['user_id'], safe_reason)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('notifications'))

if __name__ == '__main__':
    conn = get_db()
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, is_admin BOOLEAN)')
    conn.execute('CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, recipient_user_id INTEGER, sender_user_id INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_read BOOLEAN DEFAULT 0, is_blocked BOOLEAN DEFAULT 0, FOREIGN KEY(recipient_user_id) REFERENCES users(user_id), FOREIGN KEY(sender_user_id) REFERENCES users(user_id))')
    conn.execute('CREATE TABLE IF NOT EXISTS notification_reports (report_id INTEGER PRIMARY KEY AUTOINCREMENT, notification_id INTEGER, user_id INTEGER, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(notification_id) REFERENCES notifications(id), FOREIGN KEY(user_id) REFERENCES users(user_id))')
    conn.execute("INSERT OR IGNORE INTO users (user_id,username,is_admin) VALUES (1,'user',0)")
    conn.execute("INSERT OR IGNORE INTO users (user_id,username,is_admin) VALUES (2,'admin',1)")
    conn.commit()
    conn.close()
    app.run(debug=True)
