from django.conf import settings
from django.db import models
from django.urls import path
from django.http import HttpResponse, JsonResponse
from django.template import Template
from django.utils import timezone

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
    user, created = User.objects.get_or_create(user_id=user_id)
    request.session['user_id'] = user_id
    request.session['is_admin'] = user.is_admin
    return HttpResponse(status=200)

def comments_view(request):
    if request.method == 'POST':
        if 'user_id' not in request.session:
            return HttpResponse(status=401)
        content = request.POST.get('content')
        if content:
            Comment.objects.create(author_id=request.session['user_id'], content=content)
            return HttpResponse(status=200)
    comments = Comment.objects.filter(is_deleted=False).order_by('-created_at')
    html = """
    <h1>Comments</h1>
    <form method="post">
        <textarea name="content"></textarea>
        <button type="submit">Post Comment</button>
    </form>
    <ul>
    {% for comment in comments %}
        <li>
            {{ comment.author.username }} - {{ comment.content }} - {{ comment.created_at }}
            <form method="post" action="/comments/edit/{{ comment.comment_id }}/">
                <button type="submit">Edit</button>
            </form>
            <form method="post" action="/comments/delete/{{ comment.comment_id }}/">
                <button type="submit">Delete</button>
            </form>
            <form method="post" action="/comments/report/{{ comment.comment_id }}/">
                <textarea name="reason"></textarea>
                <button type="submit">Report</button>
            </form>
        </li>
    {% endfor %}
    </ul>
    """
    template = Template(html)
    return HttpResponse(template.render({'comments': comments}))

def edit_comment(request, comment_id):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    comment = Comment.objects.get(comment_id=comment_id)
    if comment.author_id != request.session['user_id']:
        return HttpResponse(status=403)
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            comment.content = content
            comment.updated_at = timezone.now()
            comment.save()
            return HttpResponse(status=200)
    html = """
    <form method="post">
        <textarea name="content">{{ comment.content }}</textarea>
        <button type="submit">Update</button>
    </form>
    """
    template = Template(html)
    return HttpResponse(template.render({'comment': comment}))

def delete_comment(request, comment_id):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    comment = Comment.objects.get(comment_id=comment_id)
    if comment.author_id != request.session['user_id'] and not request.session['is_admin']:
        return HttpResponse(status=403)
    comment.is_deleted = True
    comment.save()
    return HttpResponse(status=200)

def report_comment(request, comment_id):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    comment = Comment.objects.get(comment_id=comment_id)
    if request.method == 'POST':
        reason = request.POST.get('reason')
        if reason:
            CommentReport.objects.create(comment=comment, reporter_id=request.session['user_id'], reason=reason)
            return HttpResponse(status=200)
    html = """
    <form method="post">
        <textarea name="reason"></textarea>
        <button type="submit">Report</button>
    </form>
    """
    template = Template(html)
    return HttpResponse(template.render())

def admin_reports(request):
    if not request.session.get('is_admin', False):
        return HttpResponse(status=403)
    reports = CommentReport.objects.all()
    html = """
    <h1>Comment Reports</h1>
    <ul>
    {% for report in reports %}
        <li>
            {{ report.comment.content }} - Reported by {{ report.reporter.username }} - Reason: {{ report.reason }} - {{ report.created_at }}
            <form method="post" action="/comments/delete/{{ report.comment.comment_id }}/">
                <button type="submit">Delete Comment</button>
            </form>
        </li>
    {% endfor %}
    </ul>
    """
    template = Template(html)
    return HttpResponse(template.render({'reports': reports}))

urlpatterns = [
    path('login/<int:user_id>/', login_view, name='login'),
    path('comments/', comments_view, name='comments'),
    path('comments/edit/<int:comment_id>/', edit_comment, name='edit_comment'),
    path('comments/delete/<int:comment_id>/', delete_comment, name='delete_comment'),
    path('comments/report/<int:comment_id>/', report_comment, name='report_comment'),
    path('admin/comment_reports/', admin_reports, name='admin_reports'),
]

if __name__ == '__main__':
    from django.db import connection
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users' not in existing:           schema_editor.create_model(User)
        if 'comments' not in existing:        schema_editor.create_model(Comment)
        if 'comment_reports' not in existing: schema_editor.create_model(CommentReport)

    User.objects.create(username='user',  is_admin=False)
    User.objects.create(username='admin', is_admin=True)

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])