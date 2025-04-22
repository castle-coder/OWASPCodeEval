from flask import Flask, request, render_template_string, redirect, url_for, session
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# MySQL configuration
conn = pymysql.connect(
    host='localhost',
    user='mock_user',
    password='mock_password',
    db='mock_db',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

def init_db():
    with conn.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cursor.execute("DROP TABLE IF EXISTS users;")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        cursor.execute("""
            CREATE TABLE users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                is_deleted BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Insert mock admin and user
        cursor.execute("INSERT INTO users (username, email, password, is_admin) VALUES (%s, %s, %s, %s)",
                       ('admin', 'admin@example.com', generate_password_hash('adminpass'), True))
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                       ('user1', 'user1@example.com', generate_password_hash('userpass')))
        conn.commit()

init_db()

register_form = '''
<form method="POST">
    Username: <input name="username"><br>
    Email: <input name="email"><br>
    Password: <input type="password" name="password"><br>
    <input type="submit" value="Register">
</form>
'''

login_form = '''
<form method="POST">
    Username: <input name="username"><br>
    Password: <input type="password" name="password"><br>
    <input type="submit" value="Login">
</form>
'''

update_form = '''
<form method="POST">
    New Username: <input name="username" value="{{username}}"><br>
    New Email: <input name="email" value="{{email}}"><br>
    <input type="submit" value="Update">
</form>
'''

@app.route('/')
def index():
    return f"Hello, {'Admin' if session.get('is_admin') else session.get('username', 'Guest')}! <a href='/logout'>Logout</a>"

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                           (username, email, password))
            conn.commit()
        return redirect(url_for('login'))
    return render_template_string(register_form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username=%s AND is_deleted=FALSE", (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = user['is_admin']
                return redirect(url_for('index'))
    return render_template_string(login_form)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/update', methods=['GET', 'POST'])
def update():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        new_username = request.form['username']
        new_email = request.form['email']
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET username=%s, email=%s WHERE id=%s",
                           (new_username, new_email, session['user_id']))
            conn.commit()
        session['username'] = new_username
        return redirect(url_for('index'))
    return render_template_string(update_form, username=session['username'], email='')

@app.route('/delete', methods=['POST'])
def delete():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    with conn.cursor() as cursor:
        cursor.execute("UPDATE users SET is_deleted=TRUE WHERE id=%s", (session['user_id'],))
        conn.commit()
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/delete_user', methods=['GET', 'POST'])
def admin_delete_user():
    if not session.get('is_admin'):
        return "Unauthorized"
    if request.method == 'POST':
        user_id = request.form['user_id']
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET is_deleted=TRUE WHERE id=%s", (user_id,))
            conn.commit()
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, username FROM users WHERE is_deleted=FALSE AND id != %s", (session['user_id'],))
        users = cursor.fetchall()
    form_html = '<form method="POST">'
    for user in users:
        form_html += f"<input type='radio' name='user_id' value='{user['id']}'> {user['username']}<br>"
    form_html += "<input type='submit' value='Delete User'></form>"
    return form_html

if __name__ == '__main__':
    app.run(debug=True)