from flask import Flask, request, session, redirect, url_for, render_template_string, flash
import pymysql
import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Secret key for session management

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'mock_user',
    'password': 'mock_password',
    'db': 'mock_db'
}

# Connect to the database
def get_db_connection():
    return pymysql.connect(**db_config)

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = user_id
    session['is_admin'] = False
    if user_id == 'admin':
        session['is_admin'] = True
    return redirect(url_for('index'))

@app.route('/calendar', methods=['POST'])
def add_event():
    if 'user_id' not in session:
        return "You need to log in first", 401

    title = request.form['title']
    event_date = request.form['event_date']
    description = request.form['description']

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO calendars (user_id, title, event_date, description) VALUES (%s, %s, %s, %s)",
                           (session['user_id'], title, event_date, description))
            connection.commit()

    return redirect(url_for('index'))

@app.route('/calendar/edit/<event_id>', methods=['POST'])
def edit_event(event_id):
    if 'user_id' not in session:
        return "You need to log in first", 401

    title = request.form['title']
    event_date = request.form['event_date']
    description = request.form['description']

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE calendars SET title=%s, event_date=%s, description=%s WHERE id=%s AND user_id=%s",
                           (title, event_date, description, event_id, session['user_id']))
            connection.commit()

    return redirect(url_for('index'))

@app.route('/calendar/delete/<event_id>', methods=['POST'])
def delete_event(event_id):
    if 'user_id' not in session:
        return "You need to log in first", 401

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE calendars SET is_blocked=1 WHERE id=%s AND user_id=%s", (event_id, session['user_id']))
            connection.commit()

    return redirect(url_for('index'))

@app.route('/calendar/<event_id>')
def view_event(event_id):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM calendars WHERE id=%s", (event_id,))
            event = cursor.fetchone()

    return render_template_string("""
        <h1>Event Details</h1>
        <p>Title: {{ event.title }}</p>
        <p>Date: {{ event.event_date }}</p>
        <p>Description: {{ event.description }}</p>
    """, event=event)

@app.route('/admin/block/<event_id>', methods=['POST'])
def block_event(event_id):
    if 'user_id' not in session or not session['is_admin']:
        return "You need to log in as an admin first", 401

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE calendars SET is_blocked=1 WHERE id=%s", (event_id,))
            connection.commit()

    return redirect(url_for('index'))

@app.route('/calendar/report/<event_id>', methods=['POST'])
def report_event(event_id):
    if 'user_id' not in session:
        return "You need to log in first", 401

    reason = request.form['reason']

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO reports (event_id, user_id, reason) VALUES (%s, %s, %s)",
                           (event_id, session['user_id'], reason))
            connection.commit()

    return redirect(url_for('index'))

@app.route('/')
def index():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM calendars WHERE is_blocked=0")
            events = cursor.fetchall()

    return render_template_string("""
        <h1>Calendar</h1>
        <form action="/calendar" method="post">
            <label>Title:</label><br>
            <input type="text" name="title"><br>
            <label>Date:</label><br>
            <input type="datetime-local" name="event_date"><br>
            <label>Description:</label><br>
            <textarea name="description"></textarea><br>
            <input type="submit" value="Add Event">
        </form>
        <h2>Events</h2>
        <ul>
            {% for event in events %}
            <li>
                <a href="{{ url_for('view_event', event_id=event.id) }}">{{ event.title }}</a>
                <form action="/calendar/edit/{{ event.id }}" method="post">
                    <input type="hidden" name="title" value="{{ event.title }}">
                    <input type="hidden" name="event_date" value="{{ event.event_date }}">
                    <input type="hidden" name="description" value="{{ event.description }}">
                    <input type="submit" value="Edit">
                </form>
                <form action="/calendar/delete/{{ event.id }}" method="post">
                    <input type="submit" value="Delete">
                </form>
            </li>
            {% endfor %}
        </ul>
    """, events=events)

if __name__ == '__main__':
    app.run(debug=True)