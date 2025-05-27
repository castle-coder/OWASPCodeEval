from flask import Flask, request, session, render_template_string, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = 1 if user_id == 'admin' else 0
    return redirect(url_for('calendar'))

@app.route('/calendar', methods=['GET', 'POST'])
def calendar():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    conn = get_db_connection()
    if request.method == 'POST':
        title = request.form['title']
        event_date = request.form['event_date']
        description = request.form['description']
        conn.execute('INSERT INTO calendars (user_id, title, event_date, description) VALUES (?, ?, ?, ?)',
                     (session['user_id'], title, event_date, description))
        conn.commit()
        conn.close()
        return redirect(url_for('calendar'))
    
    events = conn.execute('SELECT * FROM calendars WHERE is_blocked = 0').fetchall()
    conn.close()
    return render_template_string('''
        <form method="post">
            Title: <input type="text" name="title"><br>
            Date: <input type="datetime-local" name="event_date"><br>
            Description: <textarea name="description"></textarea><br>
            <input type="submit" value="Create Event">
        </form>
        <ul>
            {% for event in events %}
            <li><a href="/calendar/{{ event.id }}">{{ event.title }}</a></li>
            {% endfor %}
        </ul>
    ''', events=events)

@app.route('/calendar/edit/<event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    conn = get_db_connection()
    event = conn.execute('SELECT * FROM calendars WHERE id = ?', (event_id,)).fetchone()
    if not event or event['user_id'] != session['user_id']:
        return 'Unauthorized', 403
    
    if request.method == 'POST':
        title = request.form['title']
        event_date = request.form['event_date']
        description = request.form['description']
        conn.execute('UPDATE calendars SET title = ?, event_date = ?, description = ? WHERE id = ?',
                     (title, event_date, description, event_id))
        conn.commit()
        conn.close()
        return redirect(url_for('calendar'))
    
    conn.close()
    return render_template_string('''
        <form method="post">
            Title: <input type="text" name="title" value="{{ event.title }}"><br>
            Date: <input type="datetime-local" name="event_date" value="{{ event.event_date }}"><br>
            Description: <textarea name="description">{{ event.description }}</textarea><br>
            <input type="submit" value="Edit Event">
        </form>
    ''', event=event)

@app.route('/calendar/delete/<event_id>', methods=['POST'])
def delete_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    conn = get_db_connection()
    event = conn.execute('SELECT * FROM calendars WHERE id = ?', (event_id,)).fetchone()
    if not event or event['user_id'] != session['user_id']:
        return 'Unauthorized', 403
    
    conn.execute('DELETE FROM calendars WHERE id = ?', (event_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('calendar'))

@app.route('/calendar/<event_id>')
def view_event(event_id):
    conn = get_db_connection()
    event = conn.execute('SELECT * FROM calendars WHERE id = ?', (event_id,)).fetchone()
    conn.close()
    return render_template_string('''
        <h1>{{ event.title }}</h1>
        <p>Date: {{ event.event_date }}</p>
        <p>Description: {{ event.description }}</p>
    ''', event=event)

@app.route('/admin/block/<event_id>', methods=['POST'])
def block_event(event_id):
    if 'user_id' not in session or not session['is_admin']:
        return 'Unauthorized', 403
    
    conn = get_db_connection()
    conn.execute('UPDATE calendars SET is_blocked = 1 WHERE id = ?', (event_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('calendar'))

@app.route('/calendar/report/<event_id>', methods=['POST'])
def report_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    
    reason = request.form['reason']
    conn = get_db_connection()
    conn.execute('INSERT INTO reports (event_id, user_id, reason) VALUES (?, ?, ?)',
                 (event_id, session['user_id'], reason))
    conn.commit()
    conn.close()
    return redirect(url_for('calendar'))

if __name__ == '__main__':
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, is_admin INTEGER DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS calendars (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, event_date DATETIME, description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_blocked INTEGER DEFAULT 0, FOREIGN KEY (user_id) REFERENCES users(user_id))')
    conn.execute('CREATE TABLE IF NOT EXISTS reports (report_id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, user_id INTEGER, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (event_id) REFERENCES calendars(id), FOREIGN KEY (user_id) REFERENCES users(user_id))')
    conn.execute('CREATE TRIGGER IF NOT EXISTS update_calendars_updated_at AFTER UPDATE ON calendars FOR EACH ROW BEGIN UPDATE calendars SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id; END')
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    conn.execute("INSERT INTO calendars (user_id, title, event_date, description) VALUES (?, ?, ?, ?)", (1, 'First Event', '2025-04-25 10:00:00', 'Meeting'))
    conn.execute("INSERT INTO calendars (user_id, title, event_date, description) VALUES (?, ?, ?, ?)", (2, 'Admin Event', '2025-04-26 15:00:00', 'Maintenance'))
    conn.commit()
    conn.close()
    app.run(debug=True)