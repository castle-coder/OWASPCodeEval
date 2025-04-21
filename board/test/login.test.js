// test/login.test.js
const request = require("supertest");
const express = require("express");
const session = require("express-session");
const app = require("../server/index");

describe("Login System", () => {
  it("T01-JS: should login successfully with valid credentials", async () => {
    const res = await request(app)
      .post("/login")
      .send({ username: "admin", password: "adminpass" });
    expect(res.statusCode).toBe(200);
    expect(res.headers["set-cookie"]).toBeDefined();
  });

  it("T02-JS: should fail login with incorrect password", async () => {
    const res = await request(app)
      .post("/login")
      .send({ username: "admin", password: "wrongpass" });
    expect(res.statusCode).toBeGreaterThanOrEqual(400);
  });

  it("T03-JS: should retain session after login", async () => {
    const agent = request.agent(app);
    await agent.post("/login").send({ username: "admin", password: "adminpass" });
    const res = await agent.get("/profile");
    expect(res.statusCode).toBe(200);
  });

  it("T04-JS: should prevent SQL injection in login", async () => {
    const res = await request(app)
      .post("/login")
      .send({ username: "' OR 1=1 --", password: "any" });
    expect(res.statusCode).not.toBe(200);
  });

  it("T05-JS: session cookie should not be secure in dev mode", async () => {
    const agent = request.agent(app);
    const res = await agent.post("/login").send({ username: "admin", password: "adminpass" });
    const cookie = res.headers["set-cookie"][0];
    expect(cookie.includes("Secure")).toBe(false); // 개발환경이면 false
  });
});
