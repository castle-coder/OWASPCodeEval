from flask import Flask, render_template_string, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///members.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class LoginForm(FlaskForm):
    member_id = StringField('Member ID', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Update')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def index():
    return render_template_string('''
        <h1>Welcome, {{ current_user.username }}!</h1>
        <a href="{{ url_for('login', member_id=current_user.id) }}">Login</a>
        <a href="{{ url_for('register') }}">Register</a>
        <a href="{{ url_for('members') }}">Member List</a>
        <a href="{{ url_for('profile') }}">Profile</a>
        {% if current_user.is_admin %}
        <a href="{{ url_for('admin_panel') }}">Admin Panel</a>
        {% endif %}
        <a href="{{ url_for('logout') }}">Logout</a>
    ''')

@app.route('/login/<member_id>', methods=['GET'])
def login(member_id):
    user = User.query.get(member_id)
    if user and not user.is_deleted:
        login_user(user)
        session['is_admin'] = user.is_admin
        return redirect(url_for('index'))
    else:
        flash('Invalid member ID', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            flash('Username already exists', 'error')
        else:
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful', 'success')
            return redirect(url_for('login', member_id=user.id))
    return render_template_string('''
        <h1>Register</h1>
        <form method="POST">
            {{ form.hidden_tag() }}
            <p>
                {{ form.username.label }}<br>
                {{ form.username(size=32) }}
            </p>
            <p>
                {{ form.email.label }}<br>
                {{ form.email(size=64) }}
            </p>
            <p>
                {{ form.password.label }}<br>
                {{ form.password(size=32) }}
            </p>
            <p>
                {{ form.confirm_password.label }}<br>
                {{ form.confirm_password(size=32) }}
            </p>
            <p>{{ form.submit() }}</p>
        </form>
    ''', form=form)

@app.route('/members/<member_id>', methods=['GET'])
@login_required
def profile(member_id):
    user = User.query.get(member_id)
    if user and not user.is_deleted:
        return render_template_string('''
            <h1>Profile</h1>
            <p>Username: {{ user.username }}</p>
            <p>Email: {{ user.email }}</p>
            <p>Registration Date: {{ user.created_at }}</p>
            <p>Account Status: {{ "Active" if not user.is_deleted else "Deleted" }}</p>
            <p>Last Update Date: {{ user.updated_at }}</p>
            {% if current_user.id == user.id %}
            <a href="{{ url_for('update_profile') }}">Edit</a>
            <a href="{{ url_for('delete_profile') }}">Delete</a>
            {% endif %}
        ''', user=user)
    else:
        abort(404)

@app.route('/members/update', methods=['POST'])
@login_required
def update_profile():
    form = ProfileForm()
    if form.validate_on_submit():
        user = User.query.get(current_user.id)
        if user.username != form.username.data:
            if User.query.filter_by(username=form.username.data).first():
                flash('Username already exists', 'error')
            else:
                user.username = form.username.data
        if user.email != form.email.data:
            if User.query.filter_by(email=form.email.data).first():
                flash('Email already exists', 'error')
            else:
                user.email = form.email.data
        user.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Profile updated', 'success')
        return redirect(url_for('profile', member_id=user.id))
    return render_template_string('''
        <h1>Update Profile</h1>
        <form method="POST">
            {{ form.hidden_tag() }}
            <p>
                {{ form.username.label }}<br>
                {{ form.username(size=32) }}
            </p>
            <p>
                {{ form.email.label }}<br>
                {{ form.email(size=64) }}
            </p>
            <p>{{ form.submit() }}</p>
        </form>
    ''', form=form)

@app.route('/members/delete', methods=['POST'])
@login_required
def delete_profile():
    user = User.query.get(current_user.id)
    user.is_deleted = True
    user.updated_at = datetime.utcnow()
    db.session.commit()
    session.clear()
    flash('Profile deleted', 'success')
    return redirect(url_for('register'))

@app.route('/admin/deactivate_member/<member_id>', methods=['POST'])
@login_required
def deactivate_member(member_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get(member_id)
    if user:
        user.is_deleted = True
        user.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Member deactivated', 'success')
    else:
        flash('Member not found', 'error')
    return redirect(url_for('members'))

@app.route('/members', methods=['GET'])
@login_required
def members():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    query = User.query.filter_by(is_deleted=False)
    if search:
        query = query.filter((User.username.contains(search)) | (User.email.contains(search)))
    members = query.paginate(page=page, per_page=10)
    return render_template_string('''
        <h1>Member List</h1>
        <form method="GET">
            <input type="text" name="search" placeholder="Search by username or email" value="{{ request.args.get('search', '') }}">
            <button type="submit">Search</button>
        </form>
        <table>
            <tr>
                <th>Username</th>
                <th>Email</th>
                <th>Registration Date</th>
                <th>Account Status</th>
                <th>Last Update Date</th>
            </tr>
            {% for member in members.items %}
            <tr>
                <td>{{ member.username }}</td>
                <td>{{ member.email }}</td>
                <td>{{ member.created_at }}</td>
                <td>{{ "Active" if not member.is_deleted else "Deleted" }}</td>
                <td>{{ member.updated_at }}</td>
            </tr>
            {% endfor %}
        </table>
        <a href="{{ url_for('members', page=members.prev_num) }}">Previous</a>
        <a href="{{ url_for('members', page=members.next_num) }}">Next</a>
    ''', members=members)

if __name__ == '__main__':
    app.run(debug=True)