from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db import connection
from django.http import HttpResponse, HttpResponseNotFound
from django.template import Template, Context
from django.template.loader import get_template
from django.urls import path
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
    try:
        user = User.objects.get(user_id=user_id)
        request.session['user_id'] = user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse("200 OK")
    except User.DoesNotExist:
        return HttpResponseNotFound("404 Not Found")

def view_events(request):
    events = Event.objects.filter(is_deleted=False)
    template = Template("""
        <ul>
        {% for event in events %}
            <li>{{ event.title }} - {{ event.user.username }} - {{ event.start_time }} - {{ event.end_time }}
                {% if request.session.is_admin %}
                <form method="post" action="{% url 'delete_event' event.event_id %}">
                    {% csrf_token %}
                    <button type="submit">Delete</button>
                </form>
                {% endif %}
            </li>
        {% endfor %}
        </ul>
    """)
    context = Context({'events': events})
    return HttpResponse(template.render(context))

def create_event(request):
    if 'user_id' not in request.session:
        return HttpResponseNotFound("404 Not Found")
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        start_time = timezone.make_aware(datetime.strptime(request.POST.get('start_time'), '%Y-%m-%dT%H:%M:%S'))
        end_time = timezone.make_aware(datetime.strptime(request.POST.get('end_time'), '%Y-%m-%dT%H:%M:%S'))
        user = User.objects.get(user_id=request.session['user_id'])
        Event.objects.create(user=user, title=title, description=description, start_time=start_time, end_time=end_time)
        return HttpResponse("200 OK")
    else:
        return HttpResponseNotFound("404 Not Found")

def event_detail(request, event_id):
    try:
        event = Event.objects.get(event_id=event_id)
        template = Template("""
            <h1>{{ event.title }}</h1>
            <p>{{ event.description }}</p>
            <p>User: {{ event.user.username }}</p>
            <p>Time Range: {{ event.start_time }} - {{ event.end_time }}</p>
        """)
        context = Context({'event': event})
        return HttpResponse(template.render(context))
    except Event.DoesNotExist:
        return HttpResponseNotFound("404 Not Found")

def delete_event(request, event_id):
    if 'user_id' not in request.session:
        return HttpResponseNotFound("404 Not Found")
    if request.method == 'POST':
        event = Event.objects.get(event_id=event_id)
        if request.session['user_id'] == event.user_id or request.session['is_admin']:
            event.is_deleted = True
            event.save()
            return HttpResponse("200 OK")
        else:
            return HttpResponseForbidden("403 Forbidden")
    else:
        return HttpResponseNotFound("404 Not Found")

urlpatterns = [
    path('login/<int:user_id>/',           login,        name='login'),
    path('events/',                        view_events,  name='view_events'),
    path('events/create/',                 create_event, name='create_event'),
    path('events/<int:event_id>/',         event_detail, name='event_detail'),
    path('events/<int:event_id>/delete/',  delete_event, name='delete_event'),
]

if __name__ == '__main__':
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users'  not in existing: schema_editor.create_model(User)
        if 'events' not in existing: schema_editor.create_model(Event)

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