from django.conf import settings
from django.db import models
from django.http import HttpResponse, HttpResponseNotFound
from django.urls import path
from django.template import Template

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
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150)
    class Meta:
        app_label = 'chat'
        db_table = 'users'

class Message(models.Model):
    message_id = models.AutoField(primary_key=True)
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'chat'
        db_table = 'messages'

def login(request, user_id):
    user = User.objects.filter(user_id=user_id).first()
    if user:
        request.session['user_id'] = user_id
        return HttpResponse(status=200)
    else:
        return HttpResponseNotFound()

def send_message(request, receiver_id):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    sender_id = request.session['user_id']
    sender = User.objects.get(user_id=sender_id)
    receiver = User.objects.get(user_id=receiver_id)
    content = request.POST.get('content')
    if content:
        Message.objects.create(sender=sender, receiver=receiver, content=content)
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=400)

def inbox(request):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    user_id = request.session['user_id']
    user = User.objects.get(user_id=user_id)
    messages = user.received_messages.all()
    template = Template('<ul>{% for message in messages %}<li>{{ message.sender.username }} - {{ message.content }} - {{ message.timestamp }}</li>{% endfor %}</ul>')
    return HttpResponse(template.render({'messages': messages}))

def outbox(request):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    user_id = request.session['user_id']
    user = User.objects.get(user_id=user_id)
    messages = user.sent_messages.all()
    template = Template('<ul>{% for message in messages %}<li>{{ message.receiver.username }} - {{ message.content }} - {{ message.timestamp }}</li>{% endfor %}</ul>')
    return HttpResponse(template.render({'messages': messages}))

urlpatterns = [
    path('login/<int:user_id>/',      login,        name='login'),
    path('send/<int:receiver_id>/',   send_message, name='send_message'),
    path('inbox/',                    inbox,        name='inbox'),
    path('outbox/',                   outbox,       name='outbox'),
]

from django.db import connection

existing = connection.introspection.table_names()
with connection.schema_editor() as schema_editor:
    if 'users'    not in existing: schema_editor.create_model(User)
    if 'messages' not in existing: schema_editor.create_model(Message)

user1 = User.objects.create(username='alice')
user2 = User.objects.create(username='bob')

from datetime import datetime
Message.objects.create(sender=user1, receiver=user2, content='Hi Bob!')
Message.objects.create(sender=user2, receiver=user1, content='Hello Alice!')

from django.core.management import execute_from_command_line
execute_from_command_line(['', 'runserver'])