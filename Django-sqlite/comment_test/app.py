from django.conf import settings
from django.db import models, connection
from django.http import HttpResponse, JsonResponse
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
        return HttpResponse('Logged in', status=200)
    else:
        return HttpResponse('User not found', status=404)

def comments_view(request):
    comments = Comment.objects.filter(is_deleted=False).select_related('author')
    html = '<h1>Comments</h1><ul>'
    for comment in comments:
        html += f'<li>{comment.author.username}: {comment.content} ({comment.created_at}) '
        html += f'<a href="/comments/edit/{comment.comment_id}/">Edit</a> | '
        html += f'<a href="/comments/delete/{comment.comment_id}/">Delete</a> | '
        html += f'<a href="/comments/report/{comment.comment_id}/">Report</a></li>'
    html += '</ul>'
    return HttpResponse(html)

def edit_comment(request, comment_id):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        user = User.objects.filter(user_id=user_id).first()
        if user:
            comment = Comment.objects.filter(comment_id=comment_id, author=user).first()
            if comment:
                comment.content = request.POST.get('content')
                comment.save()
                return HttpResponse('Comment updated', status=200)
            else:
                return HttpResponse('Not your comment', status=403)
        else:
            return HttpResponse('Not logged in', status=401)
    else:
        return HttpResponse('Method not allowed', status=405)

def delete_comment(request, comment_id):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        user = User.objects.filter(user_id=user_id).first()
        if user:
            comment = Comment.objects.filter(comment_id=comment_id, author=user).first()
            if comment:
                comment.is_deleted = True
                comment.save()
                return HttpResponse('Comment deleted', status=200)
            else:
                return HttpResponse('Not your comment', status=403)
        elif user.is_admin:
            comment = Comment.objects.filter(comment_id=comment_id).first()
            if comment:
                comment.is_deleted = True
                comment.save()
                return HttpResponse('Comment deleted', status=200)
            else:
                return HttpResponse('Comment not found', status=404)
        else:
            return HttpResponse('Not logged in or admin', status=401)
    else:
        return HttpResponse('Method not allowed', status=405)

def report_comment(request, comment_id):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        user = User.objects.filter(user_id=user_id).first()
        if user:
            comment = Comment.objects.filter(comment_id=comment_id).first()
            if comment:
                reason = request.POST.get('reason')
                CommentReport.objects.create(comment=comment, reporter=user, reason=reason)
                return HttpResponse('Reported', status=200)
            else:
                return HttpResponse('Comment not found', status=404)
        else:
            return HttpResponse('Not logged in', status=401)
    else:
        return HttpResponse('Method not allowed', status=405)

def admin_reports(request):
    if request.session.get('is_admin'):
        reports = CommentReport.objects.select_related('comment', 'reporter')
        html = '<h1>Comment Reports</h1><ul>'
        for report in reports:
            html += f'<li>{report.comment.content} by {report.reporter.username} ({report.reason}) ({report.created_at}) '
            html += f'<a href="/admin/comment_reports/delete/{report.report_id}/">Delete Comment</a></li>'
        html += '</ul>'
        return HttpResponse(html)
    else:
        return HttpResponse('Not admin', status=401)

def admin_delete_report(request, report_id):
    if request.session.get('is_admin'):
        report = CommentReport.objects.filter(report_id=report_id).first()
        if report:
            comment = report.comment
            comment.is_deleted = True
            comment.save()
            report.delete()
            return HttpResponse('Comment deleted', status=200)
        else:
            return HttpResponse('Report not found', status=404)
    else:
        return HttpResponse('Not admin', status=401)

urlpatterns = [
    path('login/<int:user_id>/', login_view, name='login'),
    path('comments/', comments_view, name='comments'),
    path('comments/edit/<int:comment_id>/', edit_comment, name='edit_comment'),
    path('comments/delete/<int:comment_id>/', delete_comment, name='delete_comment'),
    path('comments/report/<int:comment_id>/', report_comment, name='report_comment'),
    path('admin/comment_reports/', admin_reports, name='admin_reports'),
    path('admin/comment_reports/delete/<int:report_id>/', admin_delete_report, name='admin_delete_report'),
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