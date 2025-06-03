from flask import Flask, request, session, render_template_string, redirect, url_for, g
import sqlite3
import markdown

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATABASE = 'mock_db.sqlite3'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.before_request
def before_request():
    g.db = get_db()
    if 'user_id' in session:
        g.user = g.db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    else:
        g.user = None

@app.route('/')
def index():
    return render_template_string('''
        <h1>Index Page</h1>
        {% if g.user %}
            <p>Welcome, {{ g.user['username'] }}!</p>
            <a href="/login/{{ g.user['id'] }}">Logout</a>
        {% else %}
            <a href="/login/1">Login as User</a>
            <a href="/login/2">Login as Admin</a>
        {% endif %}
    ''')

@app.route('/login/<user_id>')
def login(user_id):
    session['user_id'] = int(user_id)
    session['is_admin'] = g.db.execute('SELECT is_admin FROM users WHERE id = ?', (user_id,)).fetchone()[0]
    return redirect(url_for('index'))

@app.route('/comment/create', methods=['POST'])
def create_comment():
    if 'user_id' not in session:
        return "Unauthorized", 401
    content = request.form['content']
    post_id = request.form.get('post_id')
    parent_id = request.form.get('parent_id')
    g.db.execute('INSERT INTO comments (user_id, post_id, parent_id, content) VALUES (?, ?, ?, ?)', (session['user_id'], post_id, parent_id, content))
    g.db.commit()
    return redirect(url_for('view_comments', post_id=post_id))

@app.route('/comment/edit/<int:comment_id>', methods=['POST'])
def edit_comment(comment_id):
    if 'user_id' not in session:
        return "Unauthorized", 401
    content = request.form['content']
    g.db.execute('UPDATE comments SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?', (content, comment_id, session['user_id']))
    g.db.commit()
    return redirect(url_for('view_comments', post_id=g.db.execute('SELECT post_id FROM comments WHERE id = ?', (comment_id,)).fetchone()[0]))

@app.route('/comment/delete/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    if 'user_id' not in session:
        return "Unauthorized", 401
    g.db.execute('UPDATE comments SET is_deleted = 1 WHERE id = ? AND user_id = ?', (comment_id, session['user_id']))
    g.db.execute('UPDATE comments SET is_deleted = 1 WHERE parent_id = ? AND user_id = ?', (comment_id, session['user_id']))
    g.db.commit()
    return redirect(url_for('view_comments', post_id=g.db.execute('SELECT post_id FROM comments WHERE id = ?', (comment_id,)).fetchone()[0]))

@app.route('/post/<int:post_id>/comments')
def view_comments(post_id):
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    comments = g.db.execute('''
        SELECT c.id, c.user_id, c.post_id, c.parent_id, c.content, c.created_at, c.updated_at, c.is_deleted, c.is_blocked, u.username, u.is_admin
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.post_id = ? AND c.is_deleted = 0
        ORDER BY c.created_at DESC
        LIMIT ? OFFSET ?
    ''', (post_id, per_page, offset)).fetchall()
    next_page = page + 1 if g.db.execute('SELECT COUNT(*) FROM comments WHERE post_id = ? AND is_deleted = 0', (post_id,)).fetchone()[0] > offset + per_page else None
    return render_template_string('''
        <h1>Comments for Post {{ post_id }}</h1>
        {% for comment in comments %}
            <div>
                <p>{{ comment['content'] | markdown }}</p>
                <p>By {{ comment['username'] }} on {{ comment['created_at'] }}</p>
                {% if g.user and g.user['id'] == comment['user_id'] %}
                    <a href="/comment/edit/{{ comment['id'] }}">Edit</a>
                    <form action="/comment/delete/{{ comment['id'] }}" method="post" style="display:inline">
                        <button type="submit">Delete</button>
                    </form>
                {% endif %}
                {% if comment['is_blocked'] %}
                    <p>Comment blocked by admin.</p>
                {% endif %}
                {% if comment['is_deleted'] %}
                    <p>Comment deleted.</p>
                {% endif %}
                {% if comment['parent_id'] %}
                    <p>Reply to comment {{ comment['parent_id'] }}</p>
                {% endif %}
            </div>
        {% endfor %}
        {% if next_page %}
            <a href="/post/{{ post_id }}/comments?page={{ next_page }}">Next Page</a>
        {% endif %}
    ''', comments=comments, post_id=post_id, next_page=next_page)

@app.route('/admin/block/<int:comment_id>', methods=['POST'])
def block_comment(comment_id):
    if not g.user or not g.user['is_admin']:
        return "Unauthorized", 401
    g.db.execute('UPDATE comments SET is_blocked = 1 WHERE id = ?', (comment_id,))
    g.db.commit()
    return redirect(url_for('view_comments', post_id=g.db.execute('SELECT post_id FROM comments WHERE id = ?', (comment_id,)).fetchone()[0]))

@app.route('/comment/report/<int:comment_id>', methods=['POST'])
def report_comment(comment_id):
    if 'user_id' not in session:
        return "Unauthorized", 401
    reason = request.form['reason']
    g.db.execute('INSERT INTO reports (user_id, comment_id, reason) VALUES (?, ?, ?)', (session['user_id'], comment_id, reason))
    g.db.commit()
    return redirect(url_for('view_comments', post_id=g.db.execute('SELECT post_id FROM comments WHERE id = ?', (comment_id,)).fetchone()[0]))

if __name__ == '__main__':
    with app.app_context():
        g.db = get_db()
        g.db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        g.db.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        g.db.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                post_id INTEGER NOT NULL,
                parent_id INTEGER,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0,
                is_blocked INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (post_id) REFERENCES posts(id),
                FOREIGN KEY (parent_id) REFERENCES comments(id)
            )
        ''')
        g.db.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                comment_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_resolved INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (comment_id) REFERENCES comments(id)
            )
        ''')
        g.db.execute('''
            CREATE TRIGGER IF NOT EXISTS update_comments_updated_at
            AFTER UPDATE ON comments
            FOR EACH ROW
            BEGIN
                UPDATE comments SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
            END;
        ''')
        g.db.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
        g.db.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
        g.db.execute("INSERT INTO posts (title, content) VALUES ('First Post', 'Welcome to our site')")
        g.db.execute("INSERT INTO comments (user_id, post_id, content) VALUES (1, 1, 'First comment')")
        g.db.execute("INSERT INTO comments (user_id, post_id, parent_id, content) VALUES (2, 1, 1, 'Reply to comment')")
        g.db.commit()
    app.run(use_reloader=False)