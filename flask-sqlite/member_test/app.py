# app.py
from flask import Flask, render_template_string, redirect, url_for, request, flash, session, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class UpdateForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Update')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('You must be logged in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def before_request():
    g.user = current_user

@app.route('/')
@login_required
def index():
    return render_template_string('''
        <h1>Welcome, {{ user.username }}!</h1>
        <a href="{{ url_for('login') }}">Login</a>
        <a href="{{ url_for('register') }}">Register</a>
        <a href="{{ url_for('members') }}">Member List</a>
        {% if user.is_admin %}
            <a href="{{ url_for('admin_panel') }}">Admin Panel</a>
        {% endif %}
        <a href="{{ url_for('logout') }}">Logout</a>
    ''')

@app.route('/login/<member_id>', methods=['GET'])
def login(member_id):
    user = User.query.filter_by(username=member_id).first()
    if user and not user.is_deleted:
        login_user(user)
        session['member_id'] = user.id
        session['is_admin'] = user.is_admin
        return redirect(url_for('index'))
    else:
        flash('Invalid member ID.', 'danger')
        return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('index'))

@app.route('/members/register', methods=['POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            flash('Username already exists.', 'danger')
        else:
            user = User.query.filter_by(email=form.email.data).first()
            if user:
                flash('Email already exists.', 'danger')
            else:
                user = User(username=form.username.data, email=form.email.data)
                user.set_password(form.password.data)
                db.session.add(user)
                db.session.commit()
                flash('Registration successful. Please log in.', 'success')
                return redirect(url_for('login', member_id=user.username))
    return render_template_string('''
        <form method="post">
            {{ form.csrf_token }}
            {{ form.username.label }} {{ form.username(size=20) }}
            {% for error in form.username.errors %}
                <span style="color: red;">{{ error }}</span>
            {% endfor %}
            <br>
            {{ form.email.label }} {{ form.email(size=30) }}
            {% for error in form.email.errors %}
                <span style="color: red;">{{ error }}</span>
            {% endfor %}
            <br>
            {{ form.password.label }} {{ form.password(size=20) }}
            {% for error in form.password.errors %}
                <span style="color: red;">{{ error }}</span>
            {% endfor %}
            <br>
            {{ form.confirm_password.label }} {{ form.confirm_password(size=20) }}
            {% for error in form.confirm_password.errors %}
                <span style="color: red;">{{ error }}</span>
            {% endfor %}
            <br>
            {{ form.submit() }}
        </form>
    ''', form=form)

@app.route('/members/<member_id>', methods=['GET'])
@login_required
def member(member_id):
    user = User.query.filter_by(id=member_id).first()
    if user and not user.is_deleted:
        return render_template_string('''
            <h1>Member Profile</h1>
            <p>Username: {{ user.username }}</p>
            <p>Email: {{ user.email }}</p>
            <p>Registration Date: {{ user.created_at }}</p>
            <p>Account Status: {% if user.is_deleted %}Deleted{% else %}Active{% endif %}</p>
            <p>Last Update Date: {{ user.updated_at }}</p>
            {% if user.id == current_user.id %}
                <a href="{{ url_for('update_profile') }}">Edit Profile</a>
                <a href="{{ url_for('delete_profile') }}">Delete Profile</a>
            {% endif %}
        ''', user=user)
    else:
        flash('Invalid member ID.', 'danger')
        return redirect(url_for('index'))

@app.route('/members/update', methods=['POST'])
@login_required
def update_profile():
    form = UpdateForm()
    if form.validate_on_submit():
        user = User.query.filter_by(id=current_user.id).first()
        if user:
            user.username = form.username.data
            user.email = form.email.data
            db.session.commit()
            flash('Profile updated successfully.', 'success')
            return redirect(url_for('member', member_id=user.id))
    return render_template_string('''
        <form method="post">
            {{ form.csrf_token }}
            {{ form.username.label }} {{ form.username(size=20) }}
            {% for error in form.username.errors %}
                <span style="color: red;">{{ error }}</span>
            {% endfor %}
            <br>
            {{ form.email.label }} {{ form.email(size=30) }}
            {% for error in form.email.errors %}
                <span style="color: red;">{{ error }}</span>
            {% endfor %}
            <br>
            {{ form.submit() }}
        </form>
    ''', form=form)

@app.route('/members/delete', methods=['POST'])
@login_required
def delete_profile():
    user = User.query.filter_by(id=current_user.id).first()
    if user:
        user.is_deleted = True
        session.clear()
        db.session.commit()
        flash('Profile deleted successfully.', 'success')
        return redirect(url_for('register'))
    else:
        flash('Invalid member ID.', 'danger')
        return redirect(url_for('index'))

@app.route('/admin/deactivate_member/<member_id>', methods=['POST'])
@login_required
def deactivate_member(member_id):
    if current_user.is_admin:
        user = User.query.filter_by(id=member_id).first()
        if user and user.id != current_user.id:
            user.is_deleted = True
            db.session.commit()
            flash('Member deactivated successfully.', 'success')
        else:
            flash('Invalid member ID.', 'danger')
    else:
        flash('You do not have permission to deactivate members.', 'danger')
    return redirect(url_for('members'))

@app.route('/members')
@login_required
def members():
    page = request.args.get('page', 1, type=int)
    query = User.query.filter_by(is_deleted=False)
    username = request.args.get('username')
    email = request.args.get('email')
    if username:
        query = query.filter(User.username.contains(username))
    if email:
        query = query.filter(User.email.contains(email))
    members = query.paginate(page=page, per_page=10)
    return render_template_string('''
        <h1>Member List</h1>
        <form method="get">
            {{ form.csrf_token }}
            Username: <input type="text" name="username" value="{{ request.args.get('username') }}">
            Email: <input type="text" name="email" value="{{ request.args.get('email') }}">
            <input type="submit" value="Search">
        </form>
        <table>
            <tr>
                <th>Username</th>
                <th>Email</th>
                <th>Registration Date</th>
                <th>Account Status</th>
                <th>Last Update Date</th>
                {% if current_user.is_admin %}
                    <th>Actions</th>
                {% endif %}
            </tr>
            {% for member in members.items %}
                <tr>
                    <td>{{ member.username }}</td>
                    <td>{{ member.email }}</td>
                    <td>{{ member.created_at }}</td>
                    <td>{% if member.is_deleted %}Deleted{% else %}Active{% endif %}</td>
                    <td>{{ member.updated_at }}</td>
                    {% if current_user.is_admin %}
                        <td><a href="{{ url_for('deactivate_member', member_id=member.id) }}">Deactivate</a></td>
                    {% endif %}
                </tr>
            {% endfor %}
        </table>
        <nav>
            <ul class="pagination">
                {% if members.has_prev %}
                    <li class="page-item"><a class="page-link" href="{{ url_for('members', page=members.prev_num) }}">Previous</a></li>
                {% endif %}
                {% for page_num in members.iter_pages(left_edge=1, right_edge=1, left_current=2, right_current=2) %}
                    {% if page_num %}
                        {% if page_num == members.page %}
                            <li class="page-item active"><a class="page-link" href="{{ url_for('members', page=page_num) }}">{{ page_num }}</a></li>
                        {% else %}
                            <li class="page-item"><a class="page-link" href="{{ url_for('members', page=page_num) }}">{{ page_num }}</a></li>
                        {% endif %}
                    {% else %}
                        <li class="page-item disabled"><span class="page-link">...</span></li>
                    {% endif %}
                {% endfor %}
                {% if members.has_next %}
                    <li class="page-item"><a class="page-link" href="{{ url_for('members', page=members.next_num) }}">Next</a></li>
                {% endif %}
            </ul>
        </nav>
    ''', members=members)

@app.route('/admin_panel')
@login_required
def admin_panel():
    if current_user.is_admin:
        return render_template_string('''
            <h1>Admin Panel</h1>
            <a href="{{ url_for('members') }}">Member List</a>
            <a href="{{ url_for('register') }}">Register New Member</a>
        ''')
    else:
        flash('You do not have permission to access the admin panel.', 'danger')
        return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='user').first():
            user = User(username='user', email='user@example.com')
            user.set_password('user')
            db.session.add(user)
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@example.com', is_admin=True)
            admin.set_password('admin')
            db.session.add(admin)
        db.session.commit()
    app.run(debug=True)