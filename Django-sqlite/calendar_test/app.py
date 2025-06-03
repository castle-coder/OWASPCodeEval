from django.conf import settings
from django.template import Template, Context
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
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

def login(request, user_id):
    user = User.objects.filter(user_id=user_id).first()
    if user:
        request.session['user_id'] = user.user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=404)

@csrf_exempt
def create_event(request):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        user = User.objects.filter(user_id=user_id).first()
        if not user:
            return JsonResponse({'error': 'Not logged in'}, status=401)
        title = request.POST.get('title')
        description = request.POST.get('description')
        start_time = timezone.make_aware(datetime.strptime(request.POST.get('start_time'), '%Y-%m-%dT%H:%M:%S'))
        end_time = timezone.make_aware(datetime.strptime(request.POST.get('end_time'), '%Y-%m-%dT%H:%M:%S'))
        Event.objects.create(user=user, title=title, description=description, start_time=start_time, end_time=end_time)
        return JsonResponse({'message': 'Event created'})
    return JsonResponse({'error': 'Invalid request method'}, status=405)

def view_events(request):
    events = Event.objects.filter(is_deleted=False)
    if request.session.get('is_admin'):
        events = Event.objects.all()
    html = """
    <ul>
    {% for event in events %}
        <li>
            <h3>{{ event.title }}</h3>
            <p>User: {{ event.user.username }}</p>
            <p>Time Range: {{ event.start_time }} to {{ event.end_time }}</p>
            {% if request.session.is_admin %}
                <form action="{% url 'delete_event' event.event_id %}" method="post">
                    {% csrf_token %}
                    <button type="submit">Delete</button>
                </form>
            {% endif %}
        </li>
    {% endfor %}
    </ul>
    """
    template = Template(html)
    context = Context({'events': events})
    return HttpResponse(template.render(context))

def event_detail(request, event_id):
    event = Event.objects.filter(event_id=event_id, is_deleted=False).first()
    if not event:
        return HttpResponse(status=404)
    html = """
    <h2>{{ event.title }}</h2>
    <p>User: {{ event.user.username }}</p>
    <p>Description: {{ event.description }}</p>
    <p>Time Range: {{ event.start_time }} to {{ event.end_time }}</p>
    """
    template = Template(html)
    context = Context({'event': event})
    return HttpResponse(template.render(context))

@csrf_exempt
def delete_event(request, event_id):
    if request.method == 'POST':
        event = Event.objects.filter(event_id=event_id).first()
        if not event:
            return JsonResponse({'error': 'Event not found'}, status=404)
        user_id = request.session.get('user_id')
        user = User.objects.filter(user_id=user_id).first()
        if not user:
            return JsonResponse({'error': 'Not logged in'}, status=401)
        if not user.is_admin and event.user_id != user.user_id:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        event.is_deleted = True
        event.save()
        return JsonResponse({'message': 'Event deleted'})
    return JsonResponse({'error': 'Invalid request method'}, status=405)

from django.urls import path

urlpatterns = [
    path('login/<int:user_id>/', login, name='login'),
    path('events/', view_events, name='view_events'),
    path('events/create/', create_event, name='create_event'),
    path('events/<int:event_id>/', event_detail, name='event_detail'),
    path('events/<int:event_id>/delete/', delete_event, name='delete_event'),
]

from django.db import connection

existing = connection.introspection.table_names()
with connection.schema_editor() as schema_editor:
    if 'users' not in existing: schema_editor.create_model(User)
    if 'events' not in existing: schema_editor.create_model(Event)

if __name__ == '__main__':
    user1 = User.objects.create(username='user', is_admin=False)
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