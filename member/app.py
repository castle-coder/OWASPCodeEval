from flask import Flask, request, session, redirect, url_for, render_template_string

app = Flask(__name__)
app.secret_key = 'super-secret-key'

# Mock DB
users = []
user_id_counter = 1

# HTML 템플릿
with open("templates.html", encoding="utf-8") as f:
    templates = f.read()

# 헬퍼 함수
def get_user_by_username(username):
    return next((u for u in users if u['username'] == username), None)

def get_user_by_id(user_id):
    return next((u for u in users if u['id'] == user_id), None)

@app.route('/')
def home():
    return render_template_string(templates, page='home', users=users, session=session)


@app.route('/register', methods=['GET', 'POST'])
def register():
    global user_id_counter
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if get_user_by_username(username):
            return "Username already exists!"
        users.append({
            'id': user_id_counter,
            'username': username,
            'email': email,
            'password': password,
            'is_admin': False
        })
        user_id_counter += 1
        return redirect(url_for('login'))
    return render_template_string(templates, page='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_user_by_username(username)
        if user and user['password'] == password:
            session['user_id'] = user['id']
            return redirect(url_for('home'))
        return "Login failed!"
    return render_template_string(templates, page='login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user = get_user_by_id(session.get('user_id'))
    if not user:
        return redirect(url_for('login'))
    if request.method == 'POST':
        user['username'] = request.form['username']
        user['email'] = request.form['email']
        return redirect(url_for('home'))
    return render_template_string(templates, page='profile', user=user)

@app.route('/delete', methods=['POST'])
def delete_account():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    global users
    users = [u for u in users if u['id'] != user_id]
    session.clear()
    return redirect(url_for('home'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    user = get_user_by_id(session.get('user_id'))
    if not user or not user.get('is_admin'):
        return "Access Denied"
    if request.method == 'POST':
        delete_id = int(request.form['user_id'])
        global users
        users = [u for u in users if u['id'] != delete_id]
    return render_template_string(templates, page='admin', users=users)

# 테스트용 admin 계정 추가
users.append({
    'id': 0,
    'username': 'admin',
    'email': 'admin@example.com',
    'password': 'admin',
    'is_admin': True
})

if __name__ == '__main__':
    app.run(debug=True)
