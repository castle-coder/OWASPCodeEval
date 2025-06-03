from django.conf import settings
from django.db import connection, models
from django.core.management import execute_from_command_line
from django.urls import path
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.template import Template, Context
from datetime import datetime

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
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=404)

def notifications_view(request):
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Not logged in'}, status=401)
    user_id = request.session['user_id']
    notifications = Notification.objects.filter(recipient_id=user_id, is_blocked=False)
    return JsonResponse(list(notifications.values()), safe=False)

def mark_read(request, notification_id):
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Not logged in'}, status=401)
    user_id = request.session['user_id']
    notification = Notification.objects.filter(id=notification_id, recipient_id=user_id).first()
    if notification:
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'error': 'Notification not found'}, status=404)

def delete_notification(request, notification_id):
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Not logged in'}, status=401)
    user_id = request.session['user_id']
    notification = Notification.objects.filter(id=notification_id, recipient_id=user_id).first()
    if notification:
        notification.delete()
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'error': 'Notification not found'}, status=404)

def report_notification(request, notification_id):
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Not logged in'}, status=401)
    user_id = request.session['user_id']
    user = User.objects.get(user_id=user_id)
    notification = Notification.objects.filter(id=notification_id).first()
    if notification:
        reason = request.POST.get('reason')
        NotificationReport.objects.create(notification=notification, user=user, reason=reason)
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'error': 'Notification not found'}, status=404)

def block_notification(request, notification_id):
    if 'user_id' not in request.session or not request.session['is_admin']:
        return JsonResponse({'error': 'Not logged in or not admin'}, status=401)
    notification = Notification.objects.filter(id=notification_id).first()
    if notification:
        notification.is_blocked = True
        notification.save()
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'error': 'Notification not found'}, status=404)

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

    execute_from_command_line(['', 'runserver'])