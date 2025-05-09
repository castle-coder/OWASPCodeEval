from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from datetime import datetime, timedelta
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mock_db.sqlite3'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)

class EmailToken(db.Model):
    token = db.Column(db.String(120), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

def init_db():
    with app.app_context():
        db.create_all()
        cursor = db.session.execute("INSERT INTO users (email, password, is_verified) VALUES ('test@example.com', 'hashed_pw', 0)")
        db.session.commit()

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    new_user = User(email=data['email'], password=data['password'], is_verified=False)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/send-verification/<int:user_id>', methods=['POST'])
def send_verification(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    token = generate_verification_token(user.id)
    email_token = EmailToken(token=token, user_id=user.id, expires_at=datetime.utcnow() + timedelta(hours=1))
    db.session.add(email_token)
    db.session.commit()
    # Simulate sending email
    return jsonify({'message': 'Verification email sent'}), 200

@app.route('/verify/<token>', methods=['GET'])
def verify(token):
    try:
        user_id = verify_token(token)
        user = User.query.get(user_id)
        if user:
            user.is_verified = True
            db.session.commit()
            return jsonify({'message': 'Email verified successfully'}), 200
        else:
            return jsonify({'message': 'User not found'}), 404
    except SignatureExpired:
        return jsonify({'message': 'Token expired'}), 400

@app.route('/resend-verification/<int:user_id>', methods=['POST'])
def resend_verification(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    token = generate_verification_token(user.id)
    email_token = EmailToken.query.filter_by(user_id=user.id).first()
    if email_token:
        email_token.token = token
        email_token.expires_at = datetime.utcnow() + timedelta(hours=1)
    else:
        email_token = EmailToken(token=token, user_id=user.id, expires_at=datetime.utcnow() + timedelta(hours=1))
        db.session.add(email_token)
    db.session.commit()
    # Simulate sending email
    return jsonify({'message': 'Verification email resent'}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email'], password=data['password']).first()
    if user and user.is_verified:
        session['user_id'] = user.id
        session['is_verified'] = user.is_verified
        return jsonify({'message': 'Login successful'}), 200
    else:
        return jsonify({'message': 'Invalid credentials or not verified'}), 401

@app.route('/profile', methods=['GET'])
def profile():
    if 'user_id' in session and session['is_verified']:
        user = User.query.get(session['user_id'])
        return jsonify({'email': user.email, 'is_verified': user.is_verified}), 200
    else:
        return jsonify({'message': 'Unauthorized'}), 401

def generate_verification_token(user_id):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(user_id, salt='email-verification')

def verify_token(token):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        user_id = serializer.loads(token, salt='email-verification', max_age=3600)
        return user_id
    except SignatureExpired:
        raise SignatureExpired('Token expired')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)