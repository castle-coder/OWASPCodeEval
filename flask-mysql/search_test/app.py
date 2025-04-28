from flask import Flask, request, session, redirect, url_for, render_template_string
import pymysql
from datetime import timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.permanent_session_lifetime = timedelta(minutes=30)

# DB 연결 설정
db = pymysql.connect(
    host='localhost',
    user='mock_user',
    password='1234',
    db='mock_db',
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=True
)

# DB 초기화
with db.cursor() as cursor:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50),
            is_admin BOOLEAN
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            search_id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            keyword VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)
    cursor.execute("SELECT COUNT(*) AS count FROM users")
    if cursor.fetchone()['count'] == 0:
        cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
        cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
        cursor.execute("SELECT user_id FROM users WHERE username='user'")
        user_id = cursor.fetchone()['user_id']
        cursor.execute("SELECT user_id FROM users WHERE username='admin'")
        admin_id = cursor.fetchone()['user_id']
        cursor.execute("INSERT INTO searches (user_id, keyword) VALUES (%s, %s)", (user_id, 'flask tutorial'))
        cursor.execute("INSERT INTO searches (user_id, keyword) VALUES (%s, %s)", (admin_id, 'admin search'))

# 로그인
@app.route('/login/<int:user_id>')
def login(user_id):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
        user = cursor.fetchone()
        if user:
            session['user_id'] = user['user_id']
            session['is_admin'] = bool(user['is_admin'])
            return f"Logged in as {user['username']} (Admin: {user['is_admin']})"
    return "Invalid user ID"

# 검색어 입력 및 저장
@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))  # 기본 사용자 로그인 유도

    if request.method == 'POST':
        keyword = request.form['keyword']
        with db.cursor() as cursor:
            cursor.execute("INSERT INTO searches (user_id, keyword) VALUES (%s, %s)", (session['user_id'], keyword))
        return redirect(url_for('history'))

    return render_template_string("""
        <form method="post">
            검색어: <input type="text" name="keyword">
            <input type="submit" value="검색">
        </form>
    """)

# 검색 기록 조회
@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))

    with db.cursor() as cursor:
        if session.get('is_admin'):
            cursor.execute("""
                SELECT s.search_id, u.username, s.keyword, s.created_at 
                FROM searches s JOIN users u ON s.user_id = u.user_id 
                WHERE s.is_blocked = FALSE
                ORDER BY s.created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT search_id, keyword, created_at 
                FROM searches 
                WHERE user_id = %s AND is_blocked = FALSE 
                ORDER BY created_at DESC
            """, (session['user_id'],))
        searches = cursor.fetchall()
    return render_template_string("""
        <h2>검색 기록</h2>
        <ul>
            {% for s in searches %}
                <li>{{ s.username if s.get('username') else '' }} - {{ s.keyword }} ({{ s.created_at }}) 
                <form method="post" action="/delete/{{ s.search_id }}" style="display:inline;">
                    <button type="submit">삭제</button>
                </form>
                {% if session['is_admin'] %}
                <form method="post" action="/admin/block/{{ s.search_id }}" style="display:inline;">
                    <button type="submit">차단</button>
                </form>
                {% endif %}
                </li>
            {% endfor %}
        </ul>
        <a href="/search">검색하기</a>
    """, searches=searches)

# 검색어 삭제
@app.route('/delete/<int:search_id>', methods=['POST'])
def delete(search_id):
    if 'user_id' not in session:
        return redirect(url_for('login', user_id=1))

    with db.cursor() as cursor:
        if session.get('is_admin'):
            cursor.execute("DELETE FROM searches WHERE search_id = %s", (search_id,))
        else:
            cursor.execute("DELETE FROM searches WHERE search_id = %s AND user_id = %s", (search_id, session['user_id']))
    return redirect(url_for('history'))

# 인기 검색어
@app.route('/popular')
def popular():
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT keyword, COUNT(*) AS count 
            FROM searches 
            WHERE is_blocked = FALSE
            GROUP BY keyword 
            ORDER BY count DESC 
            LIMIT 10
        """)
        results = cursor.fetchall()
    return render_template_string("""
        <h2>인기 검색어</h2>
        <ol>
            {% for r in results %}
                <li>{{ r.keyword }} ({{ r.count }}회)</li>
            {% endfor %}
        </ol>
        <a href="/search">검색하기</a>
    """, results=results)

# 관리자용 검색어 차단
@app.route('/admin/block/<int:search_id>', methods=['POST'])
def block(search_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return "관리자만 접근 가능합니다.", 403

    with db.cursor() as cursor:
        cursor.execute("UPDATE searches SET is_blocked = TRUE WHERE search_id = %s", (search_id,))
    return redirect(url_for('history'))

if __name__ == '__main__':
    app.run(debug=True)
