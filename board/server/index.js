// Node.js + Express 서버 - 세션 기반 로그인 추가
const express = require("express");
const cors = require("cors");
const mysql = require("mysql2");
const multer = require("multer");
const path = require("path");
const session = require("express-session");
const app = express();

app.use(cors({ origin: "http://localhost:3000", credentials: true }));
app.use(express.json());
app.use("/uploads", express.static(path.join(__dirname, "uploads")));

app.use(
  session({
    secret: "mysecret",
    resave: false,
    saveUninitialized: true,
    cookie: { secure: false } // 개발 환경에서는 true 아님
  })
);

const upload = multer({ dest: "uploads/" });

const db = mysql.createConnection({
  host: "localhost",
  user: "root",
  password: "",
  database: "vuln_board"
});

db.connect((err) => {
  if (err) console.error("DB 연결 실패", err);
  else console.log("MySQL 연결 성공");
});

// 회원가입
app.post("/register", (req, res) => {
  const { username, password } = req.body;
  db.query("SELECT * FROM users WHERE username = ?", [username], (err, results) => {
    if (err) return res.status(500).send("DB 에러");
    if (results.length > 0) return res.status(400).send("Username already exists");

    db.query("INSERT INTO users (username, password) VALUES (?, ?)", [username, password], (err2) => {
      if (err2) return res.status(500).send("DB 에러");
      res.send("Registered successfully");
    });
  });
});

// 로그인 (세션 저장)
app.post("/login", (req, res) => {
  const { username, password } = req.body;
  const query = `SELECT * FROM users WHERE username = '${username}' AND password = '${password}'`;
  db.query(query, (err, results) => {
    if (err) return res.status(500).send("DB 에러");
    if (results.length > 0) {
      req.session.user = results[0];
      res.send("Login success");
    } else {
      res.status(401).send("Login failed");
    }
  });
});

// 로그아웃 (세션 제거)
app.post("/logout", (req, res) => {
  req.session.destroy(() => {
    res.send("Logged out");
  });
});

// 로그인 여부 확인
app.get("/me", (req, res) => {
  if (req.session.user) res.json(req.session.user);
  else res.status(401).send("Not logged in");
});

// 게시글 작성 (세션 인증 필요)
app.post("/posts", upload.single("file"), (req, res) => {
  if (!req.session.user) return res.status(401).send("Not authenticated");
  const { title, content } = req.body;
  const filename = req.file ? req.file.filename : null;
  db.query(
    "INSERT INTO posts (title, content, filename) VALUES (?, ?, ?)", 
    [title, content, filename], 
    (err, result) => {
      if (err) return res.status(500).send("DB 에러");
      res.status(201).json({id: result.insertId});
  });
});

// 게시글 목록
app.get("/posts", (req, res) => {
  db.query("SELECT * FROM posts ORDER BY id DESC LIMIT 10", (err, results) => {
    if (err) return res.status(500).send("DB 에러");
    res.json(results);
  });
});

app.get("/posts/:id", (req, res) => {

  console.log("🟡 요청된 id:", req.params.id);
  console.log("🟡 세션:", req.session);
  console.log("🟡 유저:", req.session.user);

  if (!req.session.user) return res.status(401).send("Not authenticated");

  const id = req.params.id;
  db.query("SELECT * FROM posts WHERE id = ?", [id], (err, results) => {
    if (err) return res.status(500).send("DB 에러");
    if (results.length === 0) return res.status(404).send("Not found");
    res.json(results[0]);
  });
});

// 게시글 삭제 (세션 인증 필요)
app.delete("/posts/:id", (req, res) => {
  if (!req.session.user) return res.status(401).send("Not authenticated");
  const id = req.params.id;
  db.query("DELETE FROM posts WHERE id = ?", [id], (err) => {
    if (err) return res.status(500).send("DB 에러");
    res.send("deleted");
  });
});

app.listen(4000, () => {
  console.log("Server running on http://localhost:4000");
});
