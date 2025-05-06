from fastapi import FastAPI, Request, Form, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import sqlite3
import bleach
import logging
from itsdangerous import BadData

logger = logging.getLogger("uvicorn.error")
app = FastAPI()

# ——————————————————————————————
# 세션 미들웨어 (itsdangerous로 서명/검증)
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

# A8: 세션 쿠키 위조 시 BadData 예외 -> 401 Unauthorized
@app.middleware("http")
async def catch_invalid_session(request: Request, call_next):
    try:
        return await call_next(request)
    except BadData:
        request.session.clear()
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid session"}
        )

# ——————————————————————————————
# DB 초기화
DATABASE = "mock_db.sqlite3"
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # users, events, rsvps
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            is_admin BOOLEAN
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_cancelled BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rsvps (
            rsvp_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            user_id INTEGER,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # A9: reports 테이블(오직 content 컬럼)
    cursor.execute('DROP TABLE IF EXISTS reports')
    cursor.execute('''
        CREATE TABLE reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # 샘플 데이터
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, is_admin) VALUES (1, 'alice', 0)")
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, is_admin) VALUES (2, 'admin', 1)")
    cursor.execute("INSERT OR IGNORE INTO events (id, user_id, title, description, start_time, end_time) VALUES (1, 1, 'Meeting', 'Team sync-up', '2025-05-10 10:00:00', '2025-05-10 11:00:00')")
    cursor.execute("INSERT OR IGNORE INTO events (id, user_id, title, description, start_time, end_time) VALUES (2, 2, 'Admin Review', 'Quarterly review', '2025-05-15 14:00:00', '2025-05-15 15:30:00')")
    cursor.execute("INSERT OR IGNORE INTO rsvps (rsvp_id, event_id, user_id, status) VALUES (1, 1, 2, 'yes')")

    conn.commit()
    conn.close()

init_db()

templates = Jinja2Templates(directory="templates")

# ——————————————————————————————
# 로그인: 세션에 user_id/is_admin 저장, 307 리다이렉트
@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    request.session.clear()
    request.session["user_id"] = user_id
    # 실제 권한 검사를 위해선 DB 조회 후 설정할 수 있습니다.
    request.session["is_admin"] = False
    return RedirectResponse(url="/calendar", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

# ——————————————————————————————
# A3/A7: 이벤트 생성 (파라미터라이즈드 SQL + bleach.clean)
@app.post("/calendar")
async def create_event(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...)
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")

    safe_title = bleach.clean(title)
    safe_desc = bleach.clean(description)

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO events (user_id, title, description, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
        (user_id, safe_title, safe_desc, start_time, end_time)
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/calendar", status_code=status.HTTP_302_FOUND)

# A1: 수정 권한 체크 (404 → 403 분리)
@app.post("/calendar/edit/{event_id}")
async def edit_event(
    request: Request,
    event_id: int,
    title: str = Form(...),
    description: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...)
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if row[0] != user_id:
        conn.close()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    safe_title = bleach.clean(title)
    safe_desc = bleach.clean(description)
    cursor.execute(
        "UPDATE events SET title = ?, description = ?, start_time = ?, end_time = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (safe_title, safe_desc, start_time, end_time, event_id)
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/calendar", status_code=status.HTTP_302_FOUND)

# 삭제도 소유자만
@app.post("/calendar/delete/{event_id}")
async def delete_event(request: Request, event_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if row[0] != user_id:
        conn.close()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    cursor.execute("UPDATE events SET is_cancelled = 1 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/calendar", status_code=status.HTTP_302_FOUND)

# ——————————————————————————————
# A8: 조회 전에도 로그인 필수화
@app.get("/calendar")
async def view_events(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE is_cancelled = 0")
    events = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("events.html", {"request": request, "events": events})

@app.get("/calendar/{event_id}")
async def view_event(request: Request, event_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    cursor.execute("SELECT * FROM rsvps WHERE event_id = ?", (event_id,))
    rsvps = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("event.html", {"request": request, "event": event, "rsvps": rsvps})

# RSVP 역시 로그인 필요
@app.post("/calendar/rsvp/{event_id}")
async def rsvp_to_event(request: Request, event_id: int, status: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO rsvps (event_id, user_id, status) VALUES (?, ?, ?)",
        (event_id, user_id, status)
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/calendar/{event_id}", status_code=status.HTTP_302_FOUND)

# ——————————————————————————————
# A9: 신고 기능 – content만 받아서 INSERT, 302 리다이렉트
@app.post("/report")
async def report_event(request: Request, content: str = Form(...)):
    # 로그인 안 해도 허용 (user_id는 None 가능)
    safe_content = bleach.clean(content)

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reports (user_id, content) VALUES (?, ?)",
        (request.session.get("user_id"), safe_content)
    )
    conn.commit()
    conn.close()

    logger.info(f"Report saved: user={request.session.get('user_id')} content={safe_content}")
    return RedirectResponse(url="/calendar", status_code=status.HTTP_302_FOUND)

# ——————————————————————————————
# A10: 관리자 전용 엔드포인트
@app.post("/admin/cancel/{event_id}")
async def cancel_event(request: Request, event_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    if not request.session.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET is_cancelled = 1 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/calendar", status_code=status.HTTP_302_FOUND)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
