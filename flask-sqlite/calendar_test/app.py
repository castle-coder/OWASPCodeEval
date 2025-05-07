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
    session['is_admin'] = user_id == 'admin'
    return redirect(url_for('calendar'))

@app.route('/calendar', methods=['GET', 'POST'])
def calendar():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id='user'))
    if request.method == 'POST':
        title = request.form['title']
        event_date = request.form['event_date']
        description = request.form['description']
        conn = get_db_connection()
        conn.execute('INSERT INTO calendars (user_id, title, event_date, description) VALUES (?, ?, ?, ?)',
                     (session['user_id'], title, event_date, description))
        conn.commit()
        conn.close()
    conn = get_db_connection()
    events = conn.execute('SELECT * FROM calendars WHERE is_blocked = 0').fetchall()
    conn.close()
    return render_template_string('''
        <h1>Calendar</h1>
        <form method="post">
            <input type="text" name="title" placeholder="Title" required>
            <input type="datetime-local" name="event_date" required>
            <textarea name="description" placeholder="Description" required></textarea>
            <button type="submit">Create Event</button>
        </form>
        <ul>
            {% for event in events %}
            <li>
                <a href="/calendar/{{ event.id }}">{{ event.title }}</a>
                {% if event.user_id == session.user_id %}
                <form method="post" action="/calendar/edit/{{ event.id }}">
                    <button type="submit">Edit</button>
                </form>
                <form method="post" action="/calendar/delete/{{ event.id }}">
                    <button type="submit">Delete</button>
                </form>
                {% endif %}
            </li>
            {% endfor %}
        </ul>
    ''', events=events)

@app.route('/calendar/edit/<event_id>', methods=['POST'])
def edit_event(event_id):
    title = request.form['title']
    event_date = request.form['event_date']
    description = request.form['description']
    conn = get_db_connection()
    conn.execute('UPDATE calendars SET title = ?, event_date = ?, description = ? WHERE id = ?',
                 (title, event_date, description, event_id))
    conn.commit()
    conn.close()
    return redirect(url_for('calendar'))

@app.route('/calendar/delete/<event_id>', methods=['POST'])
def delete_event(event_id):
    conn = get_db_connection()
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
        <p>{{ event.description }}</p>
        <p>Date: {{ event.event_date }}</p>
        <p>Created at: {{ event.created_at }}</p>
        <p>Updated at: {{ event.updated_at }}</p>
    ''', event=event)

@app.route('/admin/block/<event_id>', methods=['POST'])
def block_event(event_id):
    if not session.get('is_admin'):
        return redirect(url_for('calendar'))
    conn = get_db_connection()
    conn.execute('UPDATE calendars SET is_blocked = 1 WHERE id = ?', (event_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('calendar'))

@app.route('/calendar/report/<event_id>', methods=['POST'])
def report_event(event_id):
    reason = request.form['reason']
    conn = get_db_connection()
    conn.execute('INSERT INTO reports (event_id, user_id, reason) VALUES (?, ?, ?)',
                 (event_id, session['user_id'], reason))
    conn.commit()
    conn.close()
    return redirect(url_for('calendar'))

if __name__ == '__main__':
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INT PRIMARY KEY AUTO_INCREMENT, username VARCHAR(50), is_admin BOOLEAN)')
    conn.execute('CREATE TABLE IF NOT EXISTS calendars (id INT PRIMARY KEY AUTO_INCREMENT, user_id INT, title VARCHAR(255), event_date DATETIME, description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, is_blocked BOOLEAN DEFAULT FALSE, FOREIGN KEY (user_id) REFERENCES users(user_id))')
    conn.execute('CREATE TABLE IF NOT EXISTS reports (report_id INT PRIMARY KEY AUTO_INCREMENT, event_id INT, user_id INT, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (event_id) REFERENCES calendars(id), FOREIGN KEY (user_id) REFERENCES users(user_id))')
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    conn.execute("INSERT INTO calendars (user_id, title, event_date, description) VALUES (?, ?, ?, ?)", (1, 'First Event', '2025-04-25 10:00:00', 'Meeting'))
    conn.execute("INSERT INTO calendars (user_id, title, event_date, description) VALUES (?, ?, ?, ?)", (2, 'Admin Event', '2025-04-26 15:00:00', 'Maintenance'))
    conn.commit()
    conn.close()
    app.run(debug=True)