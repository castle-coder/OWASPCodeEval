from flask import Flask, request, session, render_template_string, redirect, url_for, abort
import sqlite3
import html

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def init_db():
    conn = sqlite3.connect('mock_db.sqlite3')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            is_admin BOOLEAN
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            event_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS event_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    # 초기 사용자/이벤트 삽입 (중복 방지)
    c.execute("DELETE FROM users")
    c.execute("DELETE FROM events")
    c.execute("DELETE FROM event_reports")
    c.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
    c.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    c.execute(
        "INSERT INTO events (user_id, title, description, event_date) VALUES (?, ?, ?, ?)",
        (1, 'Meeting', 'Team sync', '2025-05-01')
    )
    c.execute(
        "INSERT INTO events (user_id, title, description, event_date) VALUES (?, ?, ?, ?)",
        (2, 'Holiday', 'Office closed', '2025-05-05')
    )
    conn.commit()
    conn.close()

init_db()

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = 1 if user_id == 'admin' else 0
    return redirect(url_for('calendar'))

@app.route('/calendar', methods=['GET', 'POST'])
def calendar():
    # 인증 확인
    if 'user_id' not in session:
        if request.method == 'POST':
            abort(401)
        return redirect(url_for('login', user_id='user'))

    user_id = int(session['user_id'])
    is_admin = bool(session.get('is_admin'))

    if request.method == 'POST':
        # 입력 값 HTML 이스케이프
        title = html.escape(request.form.get('title', ''), quote=True)
        description = html.escape(request.form.get('description', ''), quote=True)
        event_date = request.form.get('event_date', '')

        try:
            conn = sqlite3.connect('mock_db.sqlite3')
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO events (user_id, title, description, event_date) VALUES (?, ?, ?, ?)",
                (user_id, title, description, event_date)
            )
            conn.commit()
        except sqlite3.Error:
            pass
        finally:
            conn.close()
        return redirect(url_for('calendar'))

    # GET: 모든 이벤트 조회
    conn = sqlite3.connect('mock_db.sqlite3')
    cur = conn.cursor()
    cur.execute("SELECT * FROM events")
    events = cur.fetchall()
    conn.close()

    return render_template_string('''
        <!doctype html>
        <h1>Calendar</h1>
        <form method="POST">
            <label>Title:</label><br>
            <input type="text" name="title"><br>
            <label>Description:</label><br>
            <textarea name="description"></textarea><br>
            <label>Event Date:</label><br>
            <input type="date" name="event_date"><br>
            <input type="submit" value="Create Event">
        </form>
        <ul>
        {% for ev in events %}
            <li>
                <h2>{{ ev[2] }}</h2>
                <p>{{ ev[3] }}</p>
                <p>{{ ev[4] }}</p>
                <a href="{{ url_for('event_details', event_id=ev[0]) }}">Details</a>
                {% if is_admin %}
                <form method="POST" action="{{ url_for('block_event', event_id=ev[0]) }}" style="display:inline">
                    <button type="submit">Block</button>
                </form>
                {% endif %}
                <form method="POST" action="{{ url_for('report_event', event_id=ev[0]) }}" style="display:inline">
                    <button type="submit">Report</button>
                </form>
            </li>
        {% endfor %}
        </ul>
    ''', events=events, is_admin=is_admin)

@app.route('/calendar/details/<int:event_id>')
def event_details(event_id):
    if 'user_id' not in session:
        abort(401)
    user_id = int(session['user_id'])
    is_admin = bool(session.get('is_admin'))

    conn = sqlite3.connect('mock_db.sqlite3')
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE id=?", (event_id,))
    ev = cur.fetchone()
    conn.close()

    if not ev or ev[6]:
        abort(404)
    if not is_admin and ev[1] != user_id:
        abort(403)

    return render_template_string('''
        <!doctype html>
        <h1>{{ ev[2] }}</h1>
        <p>{{ ev[3] }}</p>
        <p>{{ ev[4] }}</p>
        <a href="{{ url_for('calendar') }}">Back</a>
    ''', ev=ev)

@app.route('/calendar/edit/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    if 'user_id' not in session:
        abort(401)
    user_id = int(session['user_id'])
    is_admin = bool(session.get('is_admin'))

    conn = sqlite3.connect('mock_db.sqlite3')
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE id=?", (event_id,))
    ev = cur.fetchone()
    conn.close()

    if not ev or ev[6]:
        abort(404)
    if not is_admin and ev[1] != user_id:
        abort(403)

    if request.method == 'POST':
        title = html.escape(request.form.get('title', ''), quote=True)
        description = html.escape(request.form.get('description', ''), quote=True)
        event_date = request.form.get('event_date', '')

        conn = sqlite3.connect('mock_db.sqlite3')
        cur = conn.cursor()
        cur.execute(
            "UPDATE events SET title=?, description=?, event_date=? WHERE id=?",
            (title, description, event_date, event_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('calendar'))

    return render_template_string('''
        <!doctype html>
        <h1>Edit Event</h1>
        <form method="POST">
            <label>Title:</label><br>
            <input type="text" name="title" value="{{ ev[2] }}"><br>
            <label>Description:</label><br>
            <textarea name="description">{{ ev[3] }}</textarea><br>
            <label>Event Date:</label><br>
            <input type="date" name="event_date" value="{{ ev[4] }}"><br>
            <input type="submit" value="Update Event">
        </form>
    ''', ev=ev)

@app.route('/calendar/delete/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if 'user_id' not in session:
        abort(401)
    user_id = int(session['user_id'])
    is_admin = bool(session.get('is_admin'))

    conn = sqlite3.connect('mock_db.sqlite3')
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM events WHERE id=?", (event_id,))
    ev = cur.fetchone()
    conn.close()

    if not ev:
        abort(404)
    if not is_admin and ev[0] != user_id:
        abort(403)

    conn = sqlite3.connect('mock_db.sqlite3')
    cur = conn.cursor()
    cur.execute("UPDATE events SET is_blocked=1 WHERE id=?", (event_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('calendar'))

@app.route('/admin/block/<int:event_id>', methods=['POST'])
def block_event(event_id):
    if 'user_id' not in session:
        abort(401)
    if not session.get('is_admin'):
        abort(403)

    conn = sqlite3.connect('mock_db.sqlite3')
    cur = conn.cursor()
    cur.execute("UPDATE events SET is_blocked=1 WHERE id=?", (event_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('calendar'))

@app.route('/calendar/report/<int:event_id>', methods=['POST'])
def report_event(event_id):
    if 'user_id' not in session:
        abort(401)
    user_id = int(session['user_id'])

    # 공격적 입력 이스케이프
    reason = html.escape(request.form.get('reason', ''), quote=True)

    try:
        conn = sqlite3.connect('mock_db.sqlite3')
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO event_reports (event_id, user_id, reason) VALUES (?, ?, ?)",
            (event_id, user_id, reason)
        )
        conn.commit()
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return redirect(url_for('calendar'))

if __name__ == '__main__':
    app.run(debug=True)
