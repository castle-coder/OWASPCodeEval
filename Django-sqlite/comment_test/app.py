from django.conf import settings
from django.db import models, connection
from django.core.management import execute_from_command_line
from django.urls import path
from django.http import HttpResponse, JsonResponse
from django.template import Template, Context
from django.utils import timezone
import json

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
    user = User.objects.filter(user_id=user_id).first()
    if user:
        request.session['user_id'] = user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=404)

def comments_view(request):
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            user_id = request.session.get('user_id')
            if user_id:
                author = User.objects.get(user_id=user_id)
                Comment.objects.create(author=author, content=content)
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Not logged in'}, status=401)
    comments = Comment.objects.filter(is_deleted=False).order_by('-created_at')
    template = Template("""
        <ul>
            {% for comment in comments %}
                <li>
                    {{ comment.author.username }} - {{ comment.content }} - {{ comment.created_at }}
                    <form method="post" action="{% url 'edit_comment' comment.comment_id %}">
                        <input type="text" name="content" value="{{ comment.content }}">
                        <button type="submit">Edit</button>
                    </form>
                    <form method="post" action="{% url 'delete_comment' comment.comment_id %}">
                        <button type="submit">Delete</button>
                    </form>
                    <form method="post" action="{% url 'report_comment' comment.comment_id %}">
                        <input type="text" name="reason">
                        <button type="submit">Report</button>
                    </form>
                </li>
            {% endfor %}
        </ul>
    """)
    context = Context({'comments': comments})
    return HttpResponse(template.render(context))

def edit_comment(request, comment_id):
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            user_id = request.session.get('user_id')
            if user_id:
                author = User.objects.get(user_id=user_id)
                comment = Comment.objects.filter(comment_id=comment_id, author=author).first()
                if comment:
                    comment.content = content
                    comment.save()
                    return JsonResponse({'status': 'success'})
                else:
                    return JsonResponse({'status': 'error', 'message': 'Not authorized'}, status=403)
            else:
                return JsonResponse({'status': 'error', 'message': 'Not logged in'}, status=401)
    return HttpResponse(status=405)

def delete_comment(request, comment_id):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        if user_id:
            user = User.objects.get(user_id=user_id)
            comment = Comment.objects.filter(comment_id=comment_id).first()
            if comment:
                if user.is_admin or comment.author == user:
                    comment.is_deleted = True
                    comment.save()
                    return JsonResponse({'status': 'success'})
                else:
                    return JsonResponse({'status': 'error', 'message': 'Not authorized'}, status=403)
            else:
                return JsonResponse({'status': 'error', 'message': 'Comment not found'}, status=404)
        else:
            return JsonResponse({'status': 'error', 'message': 'Not logged in'}, status=401)
    return HttpResponse(status=405)

def report_comment(request, comment_id):
    if request.method == 'POST':
        reason = request.POST.get('reason')
        if reason:
            user_id = request.session.get('user_id')
            if user_id:
                reporter = User.objects.get(user_id=user_id)
                comment = Comment.objects.filter(comment_id=comment_id).first()
                if comment:
                    CommentReport.objects.create(comment=comment, reporter=reporter, reason=reason)
                    return JsonResponse({'status': 'success'})
                else:
                    return JsonResponse({'status': 'error', 'message': 'Comment not found'}, status=404)
            else:
                return JsonResponse({'status': 'error', 'message': 'Not logged in'}, status=401)
    return HttpResponse(status=405)

def admin_reports(request):
    if request.session.get('is_admin'):
        reports = CommentReport.objects.all().order_by('-created_at')
        template = Template("""
            <ul>
                {% for report in reports %}
                    <li>
                        {{ report.comment.content }} - Reported by {{ report.reporter.username }} - {{ report.reason }} - {{ report.created_at }}
                        <form method="post" action="{% url 'delete_comment' report.comment.comment_id %}">
                            <button type="submit">Delete Comment</button>
                        </form>
                    </li>
                {% endfor %}
            </ul>
        """)
        context = Context({'reports': reports})
        return HttpResponse(template.render(context))
    else:
        return HttpResponse(status=403)

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

    execute_from_command_line(['', 'runserver'])