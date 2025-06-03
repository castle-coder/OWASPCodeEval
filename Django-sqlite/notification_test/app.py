from django.conf import settings
from django.db import models, connection
from django.urls import path
from django.http import HttpResponse, JsonResponse
from django.template import Template, Context

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

class Notification(models.Model):
    id          = models.AutoField(primary_key=True)
    recipient   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_notifications')
    sender      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    message     = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)
    is_read     = models.BooleanField(default=False)
    is_blocked  = models.BooleanField(default=False)
    class Meta:
        app_label = 'app'
        db_table  = 'notifications'

class NotificationReport(models.Model):
    report_id    = models.AutoField(primary_key=True)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    user         = models.ForeignKey(User, on_delete=models.CASCADE)
    reason       = models.TextField()
    created_at   = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'app'
        db_table  = 'notification_reports'

def login_view(request, user_id):
    user = User.objects.filter(user_id=user_id).first()
    if user:
        request.session['user_id'] = user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse('200 OK', status=200)
    else:
        return HttpResponse('404 Not Found', status=404)

def notifications_view(request):
    if 'user_id' not in request.session:
        return HttpResponse('401 Unauthorized', status=401)
    user = User.objects.get(user_id=request.session['user_id'])
    notifications = user.received_notifications.filter(is_blocked=False)
    html = """
    <h1>Notifications</h1>
    <ul>
    """
    for notification in notifications:
        html += f"""
        <li>
            <p>{notification.message}</p>
            <p>Timestamp: {notification.created_at}</p>
            <p>Read: {'Yes' if notification.is_read else 'No'}</p>
            <form method="post" action="{request.build_absolute_uri(f'/notifications/read/{notification.id}/')}">
                <button type="submit">Mark Read</button>
            </form>
            <form method="post" action="{request.build_absolute_uri(f'/notifications/delete/{notification.id}/')}">
                <button type="submit">Delete</button>
            </form>
            <form method="post" action="{request.build_absolute_uri(f'/notifications/report/{notification.id}/')}">
                <textarea name="reason"></textarea>
                <button type="submit">Report</button>
            </form>
        </li>
        """
    html += """
    </ul>
    """
    template = Template(html)
    context = Context({'notifications': notifications})
    return HttpResponse(template.render(context))

def mark_read(request, notification_id):
    if 'user_id' not in request.session:
        return HttpResponse('401 Unauthorized', status=401)
    notification = Notification.objects.get(id=notification_id)
    if notification.recipient_id == request.session['user_id']:
        notification.is_read = True
        notification.save()
        return HttpResponse('200 OK', status=200)
    else:
        return HttpResponse('403 Forbidden', status=403)

def delete_notification(request, notification_id):
    if 'user_id' not in request.session:
        return HttpResponse('401 Unauthorized', status=401)
    notification = Notification.objects.get(id=notification_id)
    if notification.recipient_id == request.session['user_id']:
        notification.delete()
        return HttpResponse('200 OK', status=200)
    else:
        return HttpResponse('403 Forbidden', status=403)

def block_notification(request, notification_id):
    if 'user_id' not in request.session or not request.session['is_admin']:
        return HttpResponse('401 Unauthorized', status=401)
    notification = Notification.objects.get(id=notification_id)
    notification.is_blocked = True
    notification.save()
    return HttpResponse('200 OK', status=200)

def report_notification(request, notification_id):
    if 'user_id' not in request.session:
        return HttpResponse('401 Unauthorized', status=401)
    notification = Notification.objects.get(id=notification_id)
    if request.method == 'POST':
        reason = request.POST.get('reason')
        NotificationReport.objects.create(user_id=request.session['user_id'], notification_id=notification_id, reason=reason)
        return HttpResponse('200 OK', status=200)
    else:
        return HttpResponse('405 Method Not Allowed', status=405)

urlpatterns = [
    path('login/<int:user_id>/', login_view, name='login'),
    path('notifications/', notifications_view, name='notifications'),
    path('notifications/read/<int:notification_id>/', mark_read, name='mark_read'),
    path('notifications/delete/<int:notification_id>/', delete_notification, name='delete_notification'),
    path('notifications/report/<int:notification_id>/', report_notification, name='report_notification'),
    path('admin/block_notification/<int:notification_id>/', block_notification, name='block_notification'),
]

if __name__ == '__main__':
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users' not in existing:                schema_editor.create_model(User)
        if 'notifications' not in existing:        schema_editor.create_model(Notification)
        if 'notification_reports' not in existing: schema_editor.create_model(NotificationReport)

    User.objects.create(username='user',  is_admin=False)
    User.objects.create(username='admin', is_admin=True)

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])