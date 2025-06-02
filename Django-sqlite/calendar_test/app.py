from django.conf import settings
import django
django.setup()

from django.db import models, connection, transaction
from django.http import HttpResponse, Http404, JsonResponse
from django.template import Template, Context
from django.utils import timezone
from datetime import datetime

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
    USE_TZ=True,
    TIME_ZONE='UTC',
    DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
)

import django
django.setup()

from django.db import models

class User(models.Model):
    user_id   = models.AutoField(primary_key=True)
    username  = models.CharField(max_length=150)
    is_admin  = models.BooleanField(default=False)
    class Meta:
        app_label = 'app'
        db_table  = 'users'

class Event(models.Model):
    event_id    = models.AutoField(primary_key=True)
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_time  = models.DateTimeField()
    end_time    = models.DateTimeField()
    is_deleted  = models.BooleanField(default=False)
    class Meta:
        app_label = 'app'
        db_table  = 'events'

from django.urls import path

urlpatterns = [
    path('login/<int:user_id>/',           login,        name='login'),
    path('events/',                        view_events,  name='view_events'),
    path('events/create/',                 create_event, name='create_event'),
    path('events/<int:event_id>/',         event_detail, name='event_detail'),
    path('events/<int:event_id>/delete/',  delete_event, name='delete_event'),
]

def login(request, user_id):
    try:
        user = User.objects.get(user_id=user_id)
        request.session['user_id'] = user.user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse('200')
    except User.DoesNotExist:
        return HttpResponse('404')

def create_event(request):
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    data = request.POST
    user = User.objects.get(user_id=request.session['user_id'])
    event = Event.objects.create(
        user=user,
        title=data['title'],
        description=data['description'],
        start_time=timezone.make_aware(datetime.strptime(data['start_time'], '%Y-%m-%dT%H:%M:%S')),
        end_time=timezone.make_aware(datetime.strptime(data['end_time'], '%Y-%m-%dT%H:%M:%S'))
    )
    return JsonResponse({'event_id': event.event_id})

def view_events(request):
    events = Event.objects.filter(is_deleted=False)
    template = Template("""
    <html><body>
        <h1>Events</h1>
        <ul>
            {% for event in events %}
                <li>{{ event.title }} by {{ event.user.username }} ({{ event.start_time }} - {{ event.end_time }}) {% if request.session.is_admin %}<form method="POST" action="{% url 'delete_event' event.event_id %}"><input type="submit" value="Delete"></form>{% endif %}</li>
            {% endfor %}
        </ul>
    </body></html>
    """)
    context = Context({'events': events})
    return HttpResponse(template.render(context))

def event_detail(request, event_id):
    try:
        event = Event.objects.get(event_id=event_id, is_deleted=False)
        template = Template("""
        <html><body>
            <h1>{{ event.title }}</h1>
            <p><strong>By:</strong> {{ event.user.username }}</p>
            <p><strong>Time:</strong> {{ event.start_time }} - {{ event.end_time }}</p>
            <p><strong>Description:</strong> {{ event.description }}</p>
        </body></html>
        """)
        context = Context({'event': event})
        return HttpResponse(template.render(context))
    except Event.DoesNotExist:
        raise Http404("Event not found")

def delete_event(request, event_id):
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    user = User.objects.get(user_id=request.session['user_id'])
    event = Event.objects.get(event_id=event_id)
    if event.user_id == user.user_id or user.is_admin:
        event.is_deleted = True
        event.save()
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

if __name__ == '__main__':
    from django.db import connection
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users'  not in existing: schema_editor.create_model(User)
        if 'events' not in existing: schema_editor.create_model(Event)

    from datetime import datetime
    from django.utils import timezone

    user1 = User.objects.create(username='user',  is_admin=False)
    admin = User.objects.create(username='admin', is_admin=True)

    Event.objects.create(
        user=user1,
        title='Meeting',
        description='Team sync-up',
        start_time=timezone.make_aware(datetime.strptime('2025-05-13T10:00:00', '%Y-%m-%dT%H:%M:%S')),
        end_time=timezone.make_aware(datetime.strptime('2025-05-13T11:00:00', '%Y-%m-%dT%H:%M:%S'))
    )
    Event.objects.create(
        user=admin,
        title='Admin Event',
        description='Planning session',
        start_time=timezone.make_aware(datetime.strptime('2025-05-14T14:00:00', '%Y-%m-%dT%H:%M:%S')),
        end_time=timezone.make_aware(datetime.strptime('2025-05-14T15:30:00', '%Y-%m-%dT%H:%M:%S'))
    )

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])