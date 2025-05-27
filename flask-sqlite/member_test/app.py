from flask import Flask, render_template_string, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
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

@app.before_first_request
def create_tables_and_insert_data():
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

@app.route('/login/<member_id>', methods=['GET'])
def login(member_id):
    user = User.query.filter_by(username=member_id, is_deleted=False).first()
    if user:
        login_user(user)
        session['is_admin'] = user.is_admin
        return redirect(url_for('index'))
    else:
        flash('Invalid member ID', 'danger')
        return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('index'))

@app.route('/members/register', methods=['POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            flash('Username already exists', 'danger')
        else:
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template_string('''
        <form method="post">
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
def member_profile(member_id):
    user = User.query.filter_by(id=member_id, is_deleted=False).first()
    if user:
        return render_template_string('''
            <h1>Member Profile</h1>
            <p>Username: {{ user.username }}</p>
            <p>Email: {{ user.email }}</p>
            <p>Registration Date: {{ user.created_at }}</p>
            <p>Account Status: {{ "Active" if not user.is_deleted else "Inactive" }}</p>
            <p>Last Update Date: {{ user.updated_at }}</p>
            <a href="{{ url_for('update_profile') }}">Edit Profile</a>
            <a href="{{ url_for('delete_profile') }}">Delete Profile</a>
        ''', user=user)
    else:
        abort(404)

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
            flash('Profile updated successfully', 'success')
            return redirect(url_for('member_profile', member_id=current_user.id))
    return render_template_string('''
        <form method="post">
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
    user = User.query.filter_by(id=current_user.id).first()
    if user:
        user.is_deleted = True
        session.clear()
        db.session.commit()
        flash('Profile deleted successfully', 'success')
        return redirect(url_for('register'))
    else:
        abort(404)

@app.route('/admin/deactivate_member/<member_id>', methods=['POST'])
@login_required
def deactivate_member(member_id):
    if current_user.is_admin:
        user = User.query.filter_by(id=member_id).first()
        if user and user.id != current_user.id:
            user.is_deleted = True
            db.session.commit()
            flash('Member deactivated successfully', 'success')
        else:
            flash('Invalid member ID or cannot deactivate yourself', 'danger')
    else:
        abort(403)
    return redirect(url_for('index'))

@app.route('/members')
@login_required
def member_list():
    page = request.args.get('page', 1, type=int)
    query = User.query.filter_by(is_deleted=False)
    if 'q' in request.args:
        query = query.filter(User.username.contains(request.args['q']) | User.email.contains(request.args['q']))
    members = query.paginate(page=page, per_page=10)
    return render_template_string('''
        <h1>Member List</h1>
        <form method="get">
            <input type="text" name="q" placeholder="Search by username or email">
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
                <td>{{ "Active" if not member.is_deleted else "Inactive" }}</td>
                <td>{{ member.updated_at }}</td>
            </tr>
            {% endfor %}
        </table>
        <a href="{{ url_for('export_members') }}">Export Members</a>
        <a href="{{ url_for('index') }}">Back</a>
    ''', members=members)

@app.route('/export_members')
@login_required
def export_members():
    if current_user.is_admin:
        members = User.query.filter_by(is_deleted=False).all()
        with open('members.csv', 'w') as f:
            f.write('Username,Email,Registration Date,Account Status,Last Update Date\n')
            for member in members:
                f.write(f'{member.username},{member.email},{member.created_at},{("Active" if not member.is_deleted else "Inactive")},{member.updated_at}\n')
        return 'Members exported successfully'
    else:
        abort(403)

@app.route('/')
@login_required
def index():
    return render_template_string('''
        <h1>Welcome, {{ current_user.username }}!</h1>
        <a href="{{ url_for('login', member_id=current_user.username) }}">Login</a>
        <a href="{{ url_for('register') }}">Register</a>
        <a href="{{ url_for('member_list') }}">Member List</a>
        {% if current_user.is_admin %}
        <a href="{{ url_for('admin_panel') }}">Admin Panel</a>
        {% endif %}
        <a href="{{ url_for('logout') }}">Logout</a>
    ''')

if __name__ == '__main__':
    app.run(debug=True)