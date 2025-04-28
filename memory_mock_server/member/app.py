from flask import Flask, request, render_template_string, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# 🧠 메모리 기반 가짜 DB
FAKE_DB = {
    'users': []
}

# 🛠️ 서버 시작 시 기본 유저 생성
def init_db():
    FAKE_DB['users'] = [
        {
            'id': 1,
            'username': 'admin',
            'email': 'admin@example.com',
            'password': generate_password_hash('adminpass', method='pbkdf2:sha256'),
            'is_admin': True,
            'is_deleted': False
        },
        {
            'id': 2,
            'username': 'user1',
            'email': 'user1@example.com',
            'password': generate_password_hash('user1pass', method='pbkdf2:sha256'),
            'is_admin': False,
            'is_deleted': False
        }
    ]

init_db()

# 간단한 템플릿들
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
        new_id = max(user['id'] for user in FAKE_DB['users']) + 1 if FAKE_DB['users'] else 1
        FAKE_DB['users'].append({
            'id': new_id,
            'username': request.form['username'],
            'email': request.form['email'],
            'password': generate_password_hash(request.form['password'], method='pbkdf2:sha256'),  # ✅ 비밀번호 해시 저장
            'is_admin': False,
            'is_deleted': False
        })
        return redirect(url_for('login'))
    return render_template_string(register_form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = next((u for u in FAKE_DB['users'] if u['username'] == username and not u['is_deleted']), None)
        if user and check_password_hash(user['password'], password):  # ✅ 비밀번호 해시 검증
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
    user = next((u for u in FAKE_DB['users'] if u['id'] == session['user_id']), None)
    if request.method == 'POST':
        user['username'] = request.form['username']
        user['email'] = request.form['email']
        session['username'] = user['username']
        return redirect(url_for('index'))
    return render_template_string(update_form, username=user['username'], email=user['email'])

@app.route('/delete', methods=['POST'])
def delete():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = next((u for u in FAKE_DB['users'] if u['id'] == session['user_id']), None)
    if user:
        user['is_deleted'] = True
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/delete_user', methods=['GET', 'POST'])
def admin_delete_user():
    if not session.get('is_admin'):
        return "Unauthorized", 403
    if request.method == 'POST':
        user_id = int(request.form['user_id'])
        user = next((u for u in FAKE_DB['users'] if u['id'] == user_id and not u['is_deleted']), None)
        if user:
            user['is_deleted'] = True
    users = [u for u in FAKE_DB['users'] if not u['is_deleted'] and u['id'] != session['user_id']]
    form_html = '<form method="POST">'
    for user in users:
        form_html += f"<input type='radio' name='user_id' value='{user['id']}'> {user['username']}<br>"
    form_html += "<input type='submit' value='Delete User'></form>"
    return form_html

if __name__ == '__main__':
    app.run(debug=True)
