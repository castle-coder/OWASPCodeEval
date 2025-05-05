
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates as StarletteTemplates
import os

app = FastAPI()

# Database configuration
DATABASE_URL = "sqlite:///mock_db.sqlite3"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    is_admin = Column(Boolean, default=False)

class StoredFile(Base):
    __tablename__ = "storedFiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    filename = Column(String, index=True)
    description = Column(Text)
    uploaded_at = Column(TIMESTAMP, default=datetime.utcnow)
    is_blocked = Column(Boolean, default=False)
    user = relationship("User", back_populates="files")
    reports = relationship("Report", back_populates="file")

class Report(Base):
    __tablename__ = "reports"
    report_id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("storedFiles.id"))
    user_id = Column(Integer, ForeignKey("users.user_id"))
    reason = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    file = relationship("StoredFile", back_populates="reports")
    user = relationship("User", back_populates="reports")

Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Middleware
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

# Templates
templates = Jinja2Templates(directory="templates")

# Routes
@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    request.session["user_id"] = user_id
    request.session["is_admin"] = user_id == 2
    return RedirectResponse(url="/files")

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), description: str = None, db: SessionLocal = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    file_path = os.path.join("uploads", file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    db_file = StoredFile(user_id=user_id, filename=file.filename, description=description)
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return {"filename": file.filename, "description": description}

@app.get("/download/{file_id}")
async def download_file(request: Request, file_id: int, db: SessionLocal = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
    if not db_file or db_file.is_blocked:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=os.path.join("uploads", db_file.filename), filename=db_file.filename)

@app.get("/files")
async def list_files(request: Request, db: SessionLocal = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    files = db.query(StoredFile).filter(StoredFile.is_blocked == False).all()
    return templates.TemplateResponse("files.html", {"request": request, "files": files})

@app.post("/delete/{file_id}")
async def delete_file(request: Request, file_id: int, db: SessionLocal = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    db_file = db.query(StoredFile).filter(StoredFile.id == file_id, StoredFile.user_id == user_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    os.remove(os.path.join("uploads", db_file.filename))
    db.delete(db_file)
    db.commit()
    return {"message": "File deleted"}

@app.post("/admin/block/{file_id}")
async def block_file(request: Request, file_id: int, db: SessionLocal = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id or not request.session.get("is_admin"):
        raise HTTPException(status_code=401, detail="Not authorized")
    db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    db_file.is_blocked = True
    db.commit()
    return {"message": "File blocked"}

@app.post("/report/{file_id}")
async def report_file(request: Request, file_id: int, reason: str, db: SessionLocal = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    db_report = Report(file_id=file_id, user_id=user_id, reason=reason)
    db.add(db_report)
    db.commit()
    return {"message": "File reported"}

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# HTML templates
templates = StarletteTemplates(directory="templates")

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)