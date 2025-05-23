from fastapi import FastAPI, Request, Form, HTTPException, Depends, Response
from fastapi.responses import HTMLResponse
# from fastapi.staticfiles import StaticFiles # Not used in the provided snippet
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
import sqlite3 # Import the base sqlite3 module
import os
import bleach # For HTML sanitization

# --- Application Setup ---
# A5 Fix: Disable /docs and /redoc endpoints by setting their URLs to None
app = FastAPI(docs_url=None, redoc_url=None)

# Middleware
# Important: For production, "your_super_secret_key_for_sessions" must be a strong, unique, random key
# and ideally loaded from environment variables or a secrets manager.
app.add_middleware(SessionMiddleware, secret_key="your_super_secret_key_for_sessions")

# Templates
templates = Jinja2Templates(directory="templates")

# Database
DATABASE = "mock_db.sqlite3"

# --- Constants for Security Logic ---
# For A1_BrokenAccessControl demo: specific content non-admins cannot post
ADMIN_ONLY_CONTENT_MARKER = "A1_Test_AdminOnlyCommentAttemptByUser1"
# For A9_InsufficientLoggingSQLiAttempt demo: specific string pattern to block from being stored as is
SQL_INJECTION_SIMILAR_PATTERN = "A9_Test_DROP TABLE comments;"


# --- Database Functions ---
def get_db_connection():
    conn = sqlite3.connect(DATABASE) # Use sqlite3 directly here
    conn.row_factory = sqlite3.Row   # Correctly assign sqlite3.Row
    return conn

@app.on_event("startup")
def startup():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Users table with a unique constraint on username
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT UNIQUE NOT NULL,
            is_admin  BOOLEAN NOT NULL DEFAULT 0
        );
    ''')
    # Comments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            comment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            content      TEXT NOT NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            parent_id    INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(parent_id) REFERENCES comments(comment_id)
        );
    ''')
    conn.commit()

    # Insert initial users if they don't exist
    initial_users = [
        ('user1', 0), # Non-admin for tests
        ('user2', 0), # Another non-admin
        ('admin_user', 1) # An admin user
    ]
    for username, is_admin_val in initial_users:
        try:
            cursor.execute("INSERT INTO users (username, is_admin) VALUES (?, ?)", (username, is_admin_val))
        except sqlite3.IntegrityError: # Corrected: Use sqlite3.IntegrityError
            pass # User likely already exists due to UNIQUE constraint
    conn.commit()

    # Insert some initial comments (optional, for basic UI population)
    cursor.execute("SELECT COUNT(*) FROM comments")
    # fetchone() returns a tuple (or sqlite3.Row object if row_factory is set)
    if cursor.fetchone()[0] == 0: # Access by index for tuple or Row object
        cursor.execute("INSERT INTO comments (user_id, content) VALUES (1, 'Welcome! This is an initial comment from user1.')")
        last_id = cursor.lastrowid
        if last_id: # Ensure last_id is not None or 0
             cursor.execute("INSERT INTO comments (user_id, content, parent_id) VALUES (2, 'A reply from user2.', ?)", (last_id,))
        conn.commit()
    conn.close()

# --- Route Handlers ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Fetch comments joined with user information
    cursor.execute("""
        SELECT c.comment_id, c.user_id, u.username, u.is_admin, c.content,
               strftime('%Y-%m-%d %H:%M:%S', c.created_at) as created_at_formatted,
               c.parent_id
        FROM comments c
        JOIN users u ON c.user_id = u.user_id
        ORDER BY c.created_at ASC
    """)
    raw_comments = cursor.fetchall()
    conn.close()

    # Convert fetched data to a list of dictionaries for easier template access
    # This is not strictly necessary if conn.row_factory = sqlite3.Row is used,
    # as rows can already be accessed by column name. However, explicit dicts are also fine.
    comments_for_template = [dict(row) for row in raw_comments]

    last_comment_status = request.session.get("last_comment_status", None)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "comments": comments_for_template,
        "last_comment_status": last_comment_status
    })

@app.post("/comment")
async def submit_comment(request: Request, user_id: int = Form(...), content: str = Form(...), parent_id: int = Form(None)):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Validate user existence and get admin status
    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()

    if not user_data:
        conn.close()
        request.session["last_comment_status"] = f"Error: User ID {user_id} not found."
        return RedirectResponse("/", status_code=303)

    is_user_admin = bool(user_data["is_admin"]) # Access by column name due to row_factory
    processed_content = content # Start with original content
    action_blocked = False
    blocked_reason = ""

    # A1 Fix: Block specific "admin-only" marked content if user is not admin
    if processed_content == ADMIN_ONLY_CONTENT_MARKER and not is_user_admin:
        action_blocked = True
        blocked_reason = f"Blocked: Non-admin attempt to post '{ADMIN_ONLY_CONTENT_MARKER}'."

    # A3 Fix: Sanitize HTML to prevent XSS.
    if not action_blocked:
        processed_content = bleach.clean(processed_content, tags=[], attributes={}, strip=True)

    # A9 Fix: Block specific SQLi-like pattern string from being stored as-is.
    if not action_blocked and processed_content == SQL_INJECTION_SIMILAR_PATTERN:
        action_blocked = True
        blocked_reason = f"Blocked: Attempt to store suspicious pattern '{SQL_INJECTION_SIMILAR_PATTERN}'."

    # Final check: if content is empty after processing, don't save.
    if not action_blocked and not processed_content.strip():
        action_blocked = True
        blocked_reason = "Blocked: Comment content is empty after sanitization."

    if action_blocked:
        request.session["last_comment_status"] = blocked_reason
    else:
        try:
            cursor.execute("INSERT INTO comments (user_id, content, parent_id) VALUES (?, ?, ?)",
                           (user_id, processed_content, parent_id))
            conn.commit()
            request.session["last_comment_status"] = f"Success: Comment added ('{processed_content[:30].replace(chr(10), ' ').replace(chr(13), '')}...')." # Sanitize for display in session
        except sqlite3.Error as e: # Corrected: Catch generic sqlite3.Error
            conn.rollback()
            request.session["last_comment_status"] = f"Error: Could not save comment to database. Details: {e}"
            print(f"Database error on comment submission: {e}") # Server-side logging

    conn.close()
    return RedirectResponse("/", status_code=303)


@app.get("/comments/{comment_id}", response_class=HTMLResponse)
async def view_comment(request: Request, comment_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.comment_id, c.user_id, u.username, u.is_admin, c.content,
               strftime('%Y-%m-%d %H:%M:%S', c.created_at) as created_at_formatted,
               c.parent_id
        FROM comments c
        JOIN users u ON c.user_id = u.user_id
        WHERE c.comment_id = ?
    """, (comment_id,))
    
    comment_data = cursor.fetchone()
    conn.close()

    if not comment_data:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    comment_for_template = dict(comment_data) # Convert Row object to dict for template
    return templates.TemplateResponse("comment.html", {
        "request": request,
        "comment": comment_for_template
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
