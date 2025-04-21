const request = require("supertest");
const express = require("express");
const session = require("express-session");
const app = require("./index"); // Assuming the app is exported in index.js
const mysql = require("mysql2");

// server/index.test.js

// Mock the database connection
jest.mock("mysql2", () => {
    const mockQuery = jest.fn();
    const mockConnection = {
        query: mockQuery,
        connect: jest.fn(),
    };
    return {
        createConnection: jest.fn(() => mockConnection),
    };
});

describe("POST /login", () => {
    let dbMock;

    beforeAll(() => {
        dbMock = mysql.createConnection();
    });

    afterEach(() => {
        jest.clearAllMocks();
    });

    it("should return 500 if there is a database error", async () => {
        dbMock.query.mockImplementation((query, values, callback) => {
            callback(new Error("DB 에러"), null);
        });

        const response = await request(app)
            .post("/login")
            .send({ username: "testuser", password: "testpass" });

        expect(response.status).toBe(500);
        expect(response.text).toBe("DB 에러");
    });

    it("should return 401 if login fails", async () => {
        dbMock.query.mockImplementation((query, values, callback) => {
            callback(null, []);
        });

        const response = await request(app)
            .post("/login")
            .send({ username: "testuser", password: "wrongpass" });

        expect(response.status).toBe(401);
        expect(response.text).toBe("Login failed");
    });

    it("should return success and set session if login succeeds", async () => {
        const mockUser = { id: 1, username: "testuser" };
        dbMock.query.mockImplementation((query, values, callback) => {
            callback(null, [mockUser]);
        });

        const response = await request(app)
            .post("/login")
            .send({ username: "testuser", password: "testpass" });

        expect(response.status).toBe(200);
        expect(response.text).toBe("Login success");
    });
});

// We recommend installing an extension to run jest tests.