from flask import Flask, request, render_template_string, session, redirect, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = sqlite3.connect('mock_db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return redirect(url_for('search'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        keyword = request.form['keyword']
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        offset = (page - 1) * per_page
        include_blocked = request.form.get('include_blocked', '0') == '1'

        conn = get_db_connection()
        if include_blocked:
            query = "SELECT id, user_id, title, SUBSTR(content, 1, 100) AS snippet, created_at FROM boards WHERE title LIKE ? OR content LIKE ? LIMIT ? OFFSET ?"
            params = ('%' + keyword + '%', '%' + keyword + '%', per_page, offset)
        else:
            query = "SELECT id, user_id, title, SUBSTR(content, 1, 100) AS snippet, created_at FROM boards WHERE title LIKE ? OR content LIKE ? AND is_blocked = 0 LIMIT ? OFFSET ?"
            params = ('%' + keyword + '%', '%' + keyword + '%', per_page, offset)
        posts = conn.execute(query, params).fetchall()
        conn.close()

        total_posts = conn.execute("SELECT COUNT(*) FROM boards WHERE title LIKE ? OR content LIKE ? AND (is_blocked = 0 OR ? = 1)", ('%' + keyword + '%', '%' + keyword + '%', include_blocked)).fetchone()[0]
        total_pages = (total_posts + per_page - 1) // per_page

        prev_page = page - 1 if page > 1 else None
        next_page = page + 1 if page < total_pages else None

        search_form = '''
        <form method="post">
            <input type="text" name="keyword" placeholder="Search..." required>
            <input type="checkbox" name="include_blocked"> Include Blocked Posts
            <button type="submit">Search</button>
        </form>
        '''

        post_list = ''.join(f'<li><a href="/board/{post["id"]}">{post["title"]} - {post["snippet"]}</a></li>' for post in posts)

        pagination = ''
        if prev_page:
            pagination += f'<a href="/search?page={prev_page}&per_page={per_page}">Previous</a> '
        if next_page:
            pagination += f'<a href="/search?page={next_page}&per_page={per_page}">Next</a>'

        return render_template_string(f'''
        <h1>Search Results</h1>
        {search_form}
        <ul>{post_list}</ul>
        {pagination}
        ''')

@app.route('/admin/search', methods=['GET'])
def admin_search():
    if 'user_id' not in session or not session['is_admin']:
        return redirect(url_for('index'))

    search_form = '''
    <form method="post">
        <input type="text" name="keyword" placeholder="Search..." required>
        <input type="checkbox" name="include_blocked"> Include Blocked Posts
        <button type="submit">Search</button>
    </form>
    '''

    return render_template_string(f'''
    <h1>Admin Search</h1>
    {search_form}
    ''')

@app.route('/board/<int:post_id>')
def board(post_id):
    conn = get_db_connection()
    post = conn.execute("SELECT * FROM boards WHERE id = ?", (post_id,)).fetchone()
    conn.close()
    return render_template_string(f'''
    <h1>{post["title"]}</h1>
    <p>{post["content"]}</p>
    <p>Created at: {post["created_at"]}</p>
    <p>Updated at: {post["updated_at"]}</p>
    <p>Blocked: {post["is_blocked"]}</p>
    <a href="/">Back to Search</a>
    ''')

def main():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            is_admin BOOLEAN
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('user1', 0)")
    conn.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
    conn.execute("INSERT INTO boards (user_id, title, content) VALUES (?, ?, ?)", (1, 'Search Demo', 'This content should be found when searching.'))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    main()
    app.run(debug=True)