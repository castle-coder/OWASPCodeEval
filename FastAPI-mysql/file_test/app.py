
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime
import os

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DATABASE_URL = "sqlite:///mock_db.sqlite3"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    is_admin = Column(Boolean, default=False)

class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String, index=True)
    description = Column(Text)
    uploaded_at = Column(TIMESTAMP, default=datetime.utcnow)
    is_blocked = Column(Boolean, default=False)
    user = relationship("User", back_populates="files")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    reason = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    file = relationship("File", back_populates="reports")
    user = relationship("User", back_populates="reports")

User.files = relationship("File", order_by=File.id, back_populates="user")
File.reports = relationship("Report", order_by=Report.id, back_populates="file")
User.reports = relationship("Report", order_by=Report.id, back_populates="user")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/login/{user_id}")
async def login(request: Request, user_id: int):
    request.session["user_id"] = user_id
    request.session["is_admin"] = User.get(user_id).is_admin
    return {"message": "Logged in successfully"}

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), description: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    file_path = os.path.join("uploads", file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    db = next(get_db())
    db.add(File(user_id=user_id, filename=file.filename, description=description))
    db.commit()
    db.refresh(db.query(File).filter(File.filename == file.filename).first())
    return {"message": "File uploaded successfully"}

@app.get("/download/{file_id}")
async def download_file(request: Request, file_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    db = next(get_db())
    file = db.query(File).filter(File.id == file_id).first()
    if not file or file.is_blocked:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(os.path.join("uploads", file.filename), filename=file.filename)

@app.get("/files")
async def list_files(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    db = next(get_db())
    files = db.query(File).filter(File.is_blocked == False).all()
    return templates.TemplateResponse("files.html", {"request": request, "files": files})

@app.post("/delete/{file_id}")
async def delete_file(request: Request, file_id: int):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    db = next(get_db())
    file = db.query(File).filter(File.id == file_id).first()
    if not file or file.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    os.remove(os.path.join("uploads", file.filename))
    db.delete(file)
    db.commit()
    return {"message": "File deleted successfully"}

@app.post("/admin/block/{file_id}")
async def block_file(request: Request, file_id: int):
    user_id = request.session.get("user_id")
    if not user_id or not User.get(user_id).is_admin:
        raise HTTPException(status_code=401, detail="Not logged in or not admin")
    db = next(get_db())
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    file.is_blocked = True
    db.commit()
    return {"message": "File blocked successfully"}

@app.post("/report/{file_id}")
async def report_file(request: Request, file_id: int, reason: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    db = next(get_db())
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    db.add(Report(file_id=file_id, user_id=user_id, reason=reason))
    db.commit()
    return {"message": "File reported successfully"}