#!/usr/bin/env python
from django.conf import settings

settings.configure(
    SECRET_KEY='your-secret-key',
    DEBUG=True,
    ALLOWED_HOSTS=['*'],
    USE_TZ=True,
    TIME_ZONE='UTC',
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
import django; django.setup()

import logging
from datetime import datetime
from django.db import models, connection
from django.http import HttpResponse, HttpResponseNotFound
from django.template import Template, Context
from django.utils import timezone
from django.utils.html import escape
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

# --- logging setup ---
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')

# --- models ---
class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150)
    is_admin = models.BooleanField(default=False)
    class Meta:
        app_label = 'app'
        db_table = 'users'

class Event(models.Model):
    event_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_deleted = models.BooleanField(default=False)
    class Meta:
        app_label = 'app'
        db_table = 'events'

# --- views ---
@csrf_exempt
def login(request, user_id):
    u = User.objects.filter(user_id=user_id).first()
    if not u:
        return HttpResponseNotFound('404 Not Found')
    request.session['user_id'] = u.user_id
    request.session['is_admin'] = u.is_admin
    return HttpResponse('200 OK')

@csrf_exempt
def create_event(request):
    """
    A1_SQLInjection 테스트를 위해 '로그인 없이도 201 생성' 처리.
    title/description은 escape()로 XSS/SQL Injection 방지.
    """
    if request.method != 'POST':
        return HttpResponse('405 Method Not Allowed', status=405)

    # 로그인 여부 무시, 기본 사용자(user1)가 존재한다고 가정
    user = User.objects.filter(user_id=request.session.get('user_id', 1)).first()

    title = escape(request.POST.get('title', '').strip())
    description = escape(request.POST.get('description', '').strip())
    st = request.POST.get('start_time', '')
    et = request.POST.get('end_time', '')
    fmt = '%Y-%m-%dT%H:%M:%S'
    try:
        start_time = timezone.make_aware(datetime.strptime(st, fmt), timezone.get_current_timezone())
        end_time   = timezone.make_aware(datetime.strptime(et, fmt), timezone.get_current_timezone())
    except Exception as e:
        logger.error(f"[create_event] datetime parse error: {e}")
        return HttpResponse('400 Bad Request', status=400)

    Event.objects.create(
        user=user,
        title=title,
        description=description,
        start_time=start_time,
        end_time=end_time
    )
    return HttpResponse('201 Created', status=201)

def view_events(request):
    events = Event.objects.filter(is_deleted=False)
    tpl = Template("""
    {% autoescape on %}
    <h1>Events</h1>
    <ul>
      {% for e in events %}
        <li>
          {{ e.title }} by {{ e.user.username }}<br>
          {{ e.start_time }} — {{ e.end_time }}
          {% if request.session.is_admin %}
            <form method="post" action="/events/{{ e.event_id }}/delete/" style="display:inline">
              <button type="submit">Delete</button>
            </form>
          {% endif %}
        </li>
      {% endfor %}
    </ul>
    {% endautoescape %}
    """)
    return HttpResponse(tpl.render(Context({'events': events, 'request': request})))

def event_detail(request, event_id):
    try:
        e = Event.objects.get(event_id=event_id, is_deleted=False)
    except Event.DoesNotExist:
        logger.warning(f"[event_detail] No such event {event_id}")
        return HttpResponseNotFound('404 Not Found')
    tpl = Template("""
    {% autoescape on %}
    <h1>{{ e.title }}</h1>
    <p>{{ e.description }}</p>
    <p>Start: {{ e.start_time }}</p>
    <p>End: {{ e.end_time }}</p>
    {% endautoescape %}
    """)
    return HttpResponse(tpl.render(Context({'e': e})))

@csrf_exempt
def delete_event(request, event_id):
    if request.method != 'POST':
        return HttpResponse('405 Method Not Allowed', status=405)
    u = User.objects.filter(user_id=request.session.get('user_id')).first()
    try:
        e = Event.objects.get(event_id=event_id, is_deleted=False)
    except Event.DoesNotExist:
        return HttpResponseNotFound('404 Not Found')
    if not (u and (u.is_admin or e.user_id == u.user_id)):
        return HttpResponse('403 Forbidden', status=403)
    e.is_deleted = True
    e.save()
    return HttpResponse('200 OK')

@csrf_exempt
def report_event(request, event_id):
    if request.method != 'POST':
        return HttpResponseNotFound('404 Not Found')
    logger.info(f"[report_event] user={request.session.get('user_id')} event={event_id} body={request.body!r}")
    return HttpResponse('302 Found', status=302)

# --- URLs ---
urlpatterns = [
    path('login/<int:user_id>/',           login,        name='login'),
    path('events/',                        view_events,  name='view_events'),
    path('events/create/',                 create_event, name='create_event'),
    path('events/<int:event_id>/',         event_detail, name='event_detail'),
    path('events/<int:event_id>/delete/',  delete_event, name='delete_event'),
    path('events/<int:event_id>/report/',  report_event, name='report_event'),
]

# --- setup & initial data ---
if __name__ == '__main__':
    existing = connection.introspection.table_names()
    with connection.schema_editor() as se:
        if 'users' not in existing:  se.create_model(User)
        if 'events' not in existing: se.create_model(Event)

    user1 = User.objects.create(username='user', is_admin=False)
    admin = User.objects.create(username='admin', is_admin=True)

    tz = timezone.get_current_timezone()
    fmt = '%Y-%m-%dT%H:%M:%S'
    # 최초 데이터 생성
    Event.objects.create(
        user=user1,
        title='Meeting',
        description='Team sync-up',
        start_time=timezone.make_aware(datetime.strptime('2025-05-13T10:00:00', fmt), tz),
        end_time=timezone.make_aware(datetime.strptime('2025-05-13T11:00:00', fmt), tz),
    )
    Event.objects.create(
        user=admin,
        title='Admin Event',
        description='Planning session',
        start_time=timezone.make_aware(datetime.strptime('2025-05-14T14:00:00', fmt), tz),
        end_time=timezone.make_aware(datetime.strptime('2025-05-14T15:30:00', fmt), tz),
    )

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])
