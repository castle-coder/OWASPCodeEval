from flask import Flask, request, redirect, url_for, session, render_template_string, abort
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 실제 운영 시 반드시 변경하세요!

# MySQL 연결 설정
DB_CONFIG = {
    'host': 'localhost',
    'user': 'mock_user',
    'password': 'mock_password',
    'database': 'mock_db'
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def init_db():
    """테이블 생성 및 더미 데이터 삽입 (매번 앱 시작 시 초기화)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # 기존 테이블 삭제
    cursor.execute("DROP TABLE IF EXISTS reports")
    cursor.execute("DROP TABLE IF EXISTS boards")
    cursor.execute("DROP TABLE IF EXISTS users")
    # users 테이블
    cursor.execute("""
        CREATE TABLE users (
            user_id INT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            is_admin BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    # boards 테이블
    cursor.execute("""
        CREATE TABLE boards (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    # reports 테이블
    cursor.execute("""
        CREATE TABLE reports (
            report_id INT PRIMARY KEY AUTO_INCREMENT,
            post_id INT NOT NULL,
            user_id INT NOT NULL,
            reason TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES boards(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    # 더미 데이터 삽입
    cursor.execute("INSERT INTO users (user_id, username, is_admin) VALUES (1, 'user', 0)")
    cursor.execute("INSERT INTO users (user_id, username, is_admin) VALUES (2, 'admin', 1)")
    cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (1, '첫 게시물', '이것은 첫 번째 게시물입니다.')")
    cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (2, '관리자 게시물', '관리자에 의해 작성된 게시물입니다.')")
    conn.commit()
    cursor.close()
    conn.close()

# 앱 시작 시 DB 초기화
init_db()

# ─── HTML 템플릿 ───────────────────────────────────────────────────────────────
base_nav = """
<nav>
  <a href="{{ url_for('list_boards') }}">게시판</a>
  {% if session.get('username') %}
    | {{ session['username'] }}님 
    | <a href="{{ url_for('logout') }}">로그아웃</a>
  {% else %}
    | <a href="{{ url_for('login_route', user_id=1) }}">[user 로그인]</a>
    | <a href="{{ url_for('login_route', user_id=2) }}">[admin 로그인]</a>
  {% endif %}
</nav>
<hr>
"""

list_tpl = """
<!DOCTYPE html><html><head><meta charset="utf-8"><title>게시글 목록</title></head><body>
  """ + base_nav + """
  <h1>게시글 목록</h1>
  {% if session.get('username') %}
    <p><a href="{{ url_for('create_board') }}">새 글 작성</a></p>
  {% endif %}
  <ul>
  {% for post in posts %}
    <li>
      {% if post.is_blocked %}
        <span style="color:red;">[차단]</span>
      {% endif %}
      <a href="{{ url_for('view_board', post_id=post.id) }}">{{ post.title }}</a>
      (작성자: {{ post.username }}, {{ post.created_at }})
    </li>
  {% endfor %}
  </ul>
</body></html>
"""

create_tpl = """
<!DOCTYPE html><html><head><meta charset="utf-8"><title>글 작성</title></head><body>
  """ + base_nav + """
  <h1>새 글 작성</h1>
  <form method="post">
    <p>제목: <input name="title" required></p>
    <p>내용:<br><textarea name="content" rows="10" cols="50" required></textarea></p>
    <button type="submit">등록</button>
  </form>
</body></html>
"""

edit_tpl = """
<!DOCTYPE html><html><head><meta charset="utf-8"><title>글 수정</title></head><body>
  """ + base_nav + """
  <h1>글 수정</h1>
  <form method="post">
    <p>제목: <input name="title" value="{{ post.title }}" required></p>
    <p>내용:<br><textarea name="content" rows="10" cols="50" required>{{ post.content }}</textarea></p>
    <button type="submit">수정</button>
  </form>
</body></html>
"""

detail_tpl = """
<!DOCTYPE html><html><head><meta charset="utf-8"><title>{{ post.title }}</title></head><body>
  """ + base_nav + """
  <h1>{{ post.title }}</h1>
  <p>작성자: {{ post.username }} | 작성일: {{ post.created_at }}</p>
  {% if post.is_blocked %}
    <p style="color:red;"><strong>이 게시글은 차단되었습니다.</strong></p>
  {% else %}
    <div style="white-space: pre-wrap;">{{ post.content }}</div>
    {% if session.get('user_id') == post.user_id %}
      <p>
        <a href="{{ url_for('edit_board', post_id=post.id) }}">수정</a>
        <form action="{{ url_for('delete_board', post_id=post.id) }}" method="post" style="display:inline;">
          <button type="submit">삭제</button>
        </form>
      </p>
    {% endif %}
    {% if session.get('user_id') and session.get('user_id') != post.user_id %}
      <h3>신고하기</h3>
      <form action="{{ url_for('report_board', post_id=post.id) }}" method="post">
        <textarea name="reason" rows="3" cols="40" placeholder="신고 사유" required></textarea><br>
        <button type="submit">신고</button>
      </form>
    {% endif %}
  {% endif %}
  {% if session.get('is_admin') %}
    <form action="{{ url_for('block_board', post_id=post.id) }}" method="post">
      <button type="submit">차단</button>
    </form>
  {% endif %}
</body></html>
"""

# ─── 라우트 정의 ────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('list_boards'))

# 로그인: /login/1 또는 /login/2
@app.route('/login/<int:user_id>')
def login_route(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if not user:
        return "없는 사용자입니다.", 404
    session['user_id']  = user['user_id']
    session['username'] = user['username']
    session['is_admin'] = bool(user['is_admin'])
    return redirect(url_for('list_boards'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('list_boards'))

# 게시글 목록
@app.route('/board')
def list_boards():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT b.*, u.username 
        FROM boards b 
        JOIN users u ON b.user_id=u.user_id
        ORDER BY b.created_at DESC
    """)
    posts = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template_string(list_tpl, posts=posts)

# 게시글 작성
@app.route('/board/create', methods=['GET','POST'])
def create_board():
    if 'user_id' not in session:
        return redirect(url_for('list_boards'))
    if request.method == 'POST':
        title   = request.form['title']
        content = request.form['content']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO boards (user_id, title, content) VALUES (%s,%s,%s)",
            (session['user_id'], title, content)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('list_boards'))
    return render_template_string(create_tpl)

# 게시글 상세 보기
@app.route('/board/<int:post_id>')
def view_board(post_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT b.*, u.username 
        FROM boards b 
        JOIN users u ON b.user_id=u.user_id
        WHERE b.id=%s
    """, (post_id,))
    post = cursor.fetchone()
    cursor.close()
    conn.close()
    if not post:
        abort(404)
    return render_template_string(detail_tpl, post=post)

# 게시글 수정
@app.route('/board/edit/<int:post_id>', methods=['GET','POST'])
def edit_board(post_id):
    if 'user_id' not in session:
        return redirect(url_for('list_boards'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM boards WHERE id=%s", (post_id,))
    post = cursor.fetchone()
    if not post or post['user_id'] != session['user_id']:
        abort(403)
    if request.method == 'POST':
        title   = request.form['title']
        content = request.form['content']
        cursor.execute(
            "UPDATE boards SET title=%s, content=%s WHERE id=%s",
            (title, content, post_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('view_board', post_id=post_id))
    cursor.close()
    conn.close()
    return render_template_string(edit_tpl, post=post)

# 게시글 삭제
@app.route('/board/delete/<int:post_id>', methods=['POST'])
def delete_board(post_id):
    if 'user_id' not in session:
        return redirect(url_for('list_boards'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM boards WHERE id=%s", (post_id,))
    post = cursor.fetchone()
    if not post or post['user_id'] != session['user_id']:
        abort(403)
    cursor.execute("DELETE FROM boards WHERE id=%s", (post_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('list_boards'))

# 게시글 신고
@app.route('/board/report/<int:post_id>', methods=['POST'])
def report_board(post_id):
    if 'user_id' not in session:
        return redirect(url_for('list_boards'))
    reason = request.form['reason']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reports (post_id, user_id, reason) VALUES (%s,%s,%s)",
        (post_id, session['user_id'], reason)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return "신고가 접수되었습니다.", 200

# 게시글 차단 (관리자)
@app.route('/admin/block/<int:post_id>', methods=['POST'])
def block_board(post_id):
    if not session.get('is_admin'):
        abort(403)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE boards SET is_blocked=TRUE WHERE id=%s", (post_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('view_board', post_id=post_id))

if __name__ == '__main__':
    app.run(debug=True)
