from django.conf import settings
from django.db import connection
from django.template import Template, Context
from django.http import HttpResponse
from django.urls import path

if not settings.configured:
    settings.configure(
        SECRET_KEY='your-secret-key',
        DEBUG=True,
        ALLOWED_HOSTS=['*'],
        SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
            'django.contrib.sessions',
        ],
        MIDDLEWARE=[
            'django.middleware.security.SecurityMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.common.CommonMiddleware',
        ],
        ROOT_URLCONF=__name__,
        TEMPLATES=[{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                ],
            },
        }],
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': 'mock_db.sqlite3',
            }
        },
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

import django
django.setup()

from django.contrib.auth.models import User
from django.db import models

class User(models.Model):
    user_id   = models.AutoField(primary_key=True)
    username  = models.CharField(max_length=150)
    is_admin  = models.BooleanField(default=False)
    class Meta:
        app_label = 'app'
        db_table  = 'users'

class Comment(models.Model):
    comment_id = models.AutoField(primary_key=True)
    author     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    class Meta:
        app_label = 'app'
        db_table  = 'comments'

class CommentReport(models.Model):
    report_id    = models.AutoField(primary_key=True)
    comment      = models.ForeignKey(Comment, on_delete=models.CASCADE)
    reporter     = models.ForeignKey(User, on_delete=models.CASCADE)
    reason       = models.TextField()
    created_at   = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'app'
        db_table  = 'comment_reports'

def login_view(request, user_id):
    try:
        user = User.objects.get(user_id=user_id)
        request.session['user_id'] = user.user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse("Login successful", status=200)
    except User.DoesNotExist:
        return HttpResponse("User not found", status=404)

def comments_view(request):
    comments = Comment.objects.filter(is_deleted=False)
    template = Template('''
        <h1>Comments</h1>
        <ul>
            {% for comment in comments %}
                <li>
                    <strong>{{ comment.author.username }}</strong>:
                    {{ comment.content }} ({{ comment.created_at }})
                    <form method="post" action="{% url 'edit_comment' comment.comment_id %}">
                        {% csrf_token %}
                        <input type="submit" value="Edit">
                    </form>
                    <form method="post" action="{% url 'delete_comment' comment.comment_id %}">
                        {% csrf_token %}
                        <input type="submit" value="Delete">
                    </form>
                    <form method="post" action="{% url 'report_comment' comment.comment_id %}">
                        {% csrf_token %}
                        <input type="submit" value="Report">
                    </form>
                </li>
            {% endfor %}
        </ul>
    ''')
    context = Context({'comments': comments})
    return HttpResponse(template.render(context))

def edit_comment(request, comment_id):
    if not 'user_id' in request.session:
        return HttpResponse("Not logged in", status=401)
    try:
        comment = Comment.objects.get(comment_id=comment_id, author_id=request.session['user_id'])
        if request.method == 'POST':
            comment.content = request.POST.get('content')
            comment.save()
            return HttpResponse("Comment updated", status=200)
        template = Template('''
            <h1>Edit Comment</h1>
            <form method="post">
                {% csrf_token %}
                <textarea name="content">{{ comment.content }}</textarea>
                <input type="submit" value="Update">
            </form>
        ''')
        context = Context({'comment': comment})
        return HttpResponse(template.render(context))
    except Comment.DoesNotExist:
        return HttpResponse("Comment not found", status=404)

def delete_comment(request, comment_id):
    if not 'user_id' in request.session:
        return HttpResponse("Not logged in", status=401)
    try:
        comment = Comment.objects.get(comment_id=comment_id)
        if comment.author_id == request.session['user_id'] or request.session['is_admin']:
            comment.is_deleted = True
            comment.save()
            return HttpResponse("Comment deleted", status=200)
        return HttpResponse("Unauthorized", status=403)
    except Comment.DoesNotExist:
        return HttpResponse("Comment not found", status=404)

def report_comment(request, comment_id):
    if not 'user_id' in request.session:
        return HttpResponse("Not logged in", status=401)
    try:
        comment = Comment.objects.get(comment_id=comment_id)
        if request.method == 'POST':
            reason = request.POST.get('reason')
            CommentReport.objects.create(comment=comment, reporter_id=request.session['user_id'], reason=reason)
            return HttpResponse("Comment reported", status=200)
        template = Template('''
            <h1>Report Comment</h1>
            <form method="post">
                {% csrf_token %}
                <textarea name="reason"></textarea>
                <input type="submit" value="Report">
            </form>
        ''')
        return HttpResponse(template.render())
    except Comment.DoesNotExist:
        return HttpResponse("Comment not found", status=404)

def admin_reports(request):
    if not 'user_id' in request.session or not request.session['is_admin']:
        return HttpResponse("Not authorized", status=403)
    reports = CommentReport.objects.all()
    template = Template('''
        <h1>Comment Reports</h1>
        <ul>
            {% for report in reports %}
                <li>
                    <strong>{{ report.comment.author.username }}'s comment:</strong>
                    {{ report.comment.content }} ({{ report.comment.created_at }})
                    <strong>Reporter:</strong> {{ report.reporter.username }}
                    <strong>Reason:</strong> {{ report.reason }} ({{ report.created_at }})
                    <form method="post" action="{% url 'delete_comment' report.comment.comment_id %}">
                        {% csrf_token %}
                        <input type="submit" value="Delete Comment">
                    </form>
                </li>
            {% endfor %}
        </ul>
    ''')
    context = Context({'reports': reports})
    return HttpResponse(template.render(context))

urlpatterns = [
    path('login/<int:user_id>/', login_view, name='login'),
    path('comments/', comments_view, name='comments'),
    path('comments/edit/<int:comment_id>/', edit_comment, name='edit_comment'),
    path('comments/delete/<int:comment_id>/', delete_comment, name='delete_comment'),
    path('comments/report/<int:comment_id>/', report_comment, name='report_comment'),
    path('admin/comment_reports/', admin_reports, name='admin_reports'),
]

if __name__ == '__main__':
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users' not in existing:           schema_editor.create_model(User)
        if 'comments' not in existing:        schema_editor.create_model(Comment)
        if 'comment_reports' not in existing: schema_editor.create_model(CommentReport)

    User.objects.create(username='user',  is_admin=False)
    User.objects.create(username='admin', is_admin=True)

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])