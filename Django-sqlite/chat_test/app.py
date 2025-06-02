from django.conf import settings
from django.db import models, connection
from django.http import HttpResponse, JsonResponse
from django.template import Template, Context
from django.urls import path

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
    try:
        User.objects.get(user_id=user_id)
        request.session['user_id'] = user_id
        return HttpResponse(status=200)
    except User.DoesNotExist:
        return HttpResponse(status=404)

def send_message(request, receiver_id):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    sender_id = request.session['user_id']
    sender = User.objects.get(user_id=sender_id)
    receiver = User.objects.get(user_id=receiver_id)
    content = request.POST.get('content')
    Message.objects.create(sender=sender, receiver=receiver, content=content)
    return HttpResponse(status=200)

def inbox(request):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    user_id = request.session['user_id']
    messages = Message.objects.filter(receiver_id=user_id)
    template = Template('<html><body><h1>Inbox</h1><ul>{{ messages }}</ul></body></html>')
    context = Context({'messages': [f'<li>{msg.sender.username}: {msg.content} ({msg.timestamp})</li>' for msg in messages]})
    return HttpResponse(template.render(context))

def outbox(request):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    user_id = request.session['user_id']
    messages = Message.objects.filter(sender_id=user_id)
    template = Template('<html><body><h1>Outbox</h1><ul>{{ messages }}</ul></body></html>')
    context = Context({'messages': [f'<li>{msg.receiver.username}: {msg.content} ({msg.timestamp})</li>' for msg in messages]})
    return HttpResponse(template.render(context))

urlpatterns = [
    path('login/<int:user_id>/', login, name='login'),
    path('send/<int:receiver_id>/', send_message, name='send_message'),
    path('inbox/', inbox, name='inbox'),
    path('outbox/', outbox, name='outbox'),
]

if __name__ == '__main__':
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users' not in existing: schema_editor.create_model(User)
        if 'messages' not in existing: schema_editor.create_model(Message)

    user1 = User.objects.create(username='alice')
    user2 = User.objects.create(username='bob')
    Message.objects.create(sender=user1, receiver=user2, content='Hi Bob!')
    Message.objects.create(sender=user2, receiver=user1, content='Hello Alice!')

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])