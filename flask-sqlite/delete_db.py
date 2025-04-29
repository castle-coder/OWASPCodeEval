import pymysql

# MySQL 연결 정보
db = pymysql.connect(
    host='localhost',
    user='mock_user',
    password='mock_password',
    db='mock_db',
    charset='utf8mb4',
    autocommit=True
)

def drop_tables_only():
    with db.cursor() as cursor:
        print("🔁 테이블 삭제 중...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

        tables = ['reports', 'boards', 'users', 'comments', 'likes', 'notifications', 'messages', 'friends', 'calendars']
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"🗑️ {table} 테이블 삭제됨")

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    print("✅ 모든 테이블 삭제 완료 (재생성 없음)")

# 실행
drop_tables_only()
