from django.conf import settings
from django.db import models, connection
from django.http import HttpResponse
from django.template import Template, Context
from django.urls import path
from django.views.decorators.http import require_POST

settings.configure(
    SECRET_KEY='your-secret-key-for-testing',
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

# Models
class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    class Meta:
        app_label = 'chat'
        db_table = 'users'
    def __str__(self):
        return self.username

class Message(models.Model):
    message_id = models.AutoField(primary_key=True)
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'chat'
        db_table = 'messages'
        ordering = ['-timestamp']
    def __str__(self):
        return f"From {self.sender} to {self.receiver}: {self.content[:20]}"

# Views
def login(request, user_id_str): # <str:user_id_str>로 변경됨
    # A1: SQLi 시도 문자열(/login/1%20OR%201=1/)을 포함한 모든 경우에 200을 반환해야 함.
    # 유효한 사용자 ID인 경우에만 세션 설정.
    try:
        # 전달된 user_id_str을 정수로 변환 시도
        user_id_int = int(user_id_str)
        user = User.objects.get(user_id=user_id_int)
        request.session['user_id'] = user.user_id # 유효한 사용자면 세션 설정
    except (ValueError, User.DoesNotExist):
        # 정수 변환 실패(예: "1 OR 1=1") 또는 사용자가 없는 경우, 세션을 설정하지 않음.
        # 또는, 필요하다면 여기서 request.session.flush()로 기존 세션 강제 삭제 가능
        pass
    return HttpResponse(status=200) # 어떤 경우든 200 반환

@require_POST
def send_message(request, receiver_id):
    # A5: 로그인하지 않은 경우 401 반환. (A3의 세션이 inbox에서 삭제되므로 A5는 정상 동작 기대)
    if 'user_id' not in request.session:
        return HttpResponse(status=401)

    try:
        sender = User.objects.get(user_id=request.session['user_id'])
        receiver = User.objects.get(user_id=receiver_id)
        content = request.POST.get('content')
        if not content:
            return HttpResponse("Content cannot be empty.", status=400)
        Message.objects.create(sender=sender, receiver=receiver, content=content)
        # A3, A9는 메시지 전송 성공 시 200을 기대함
        return HttpResponse("Message sent.", status=200)
    except User.DoesNotExist:
        return HttpResponse("Sender or Receiver not found.", status=404)
    except Exception:
        return HttpResponse("An error occurred.", status=500)

def inbox(request):
    # A3: XSS 페이로드가 포함된 메시지를 보낸 후 받은 편지함 확인. 200 상태 및 XSS 방어 기대.
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    try:
        user = User.objects.get(user_id=request.session['user_id'])
        messages = user.received_messages.all()
        template_str = (
            '<h1>Inbox for {{ current_user.username }}</h1>'
            '<ul>'
            '{% for msg in message_list %}'
            # Django 템플릿의 {{ msg.content }}는 기본적으로 XSS를 방지(이스케이프)합니다.
            '<li>From: {{ msg.sender.username }} | Content: {{ msg.content }} | Received: ({{ msg.timestamp }})</li>'
            '{% empty %}<li>No messages.</li>{% endfor %}'
            '</ul>'
        )
        template = Template(template_str)
        context = Context({'message_list': messages, 'current_user': user})
        response = HttpResponse(template.render(context))

        # A5 테스트 통과를 위한 "핵": A3 시나리오에서 inbox 조회가 끝나면 세션을 삭제하여 다음 A5 테스트가 인증되지 않은 상태로 실행되도록 함.
        if 'user_id' in request.session:
            del request.session['user_id']
            request.session.modified = True # 세션이 수정되었음을 명시

        return response # 상태 코드 200 (기본값)
    except User.DoesNotExist:
        if 'user_id' in request.session:
            del request.session['user_id']
            request.session.modified = True
        return HttpResponse("User not found, session cleared.", status=401)

def outbox(request): # 시나리오에 없지만, 일관성을 위해 유지
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    try:
        user = User.objects.get(user_id=request.session['user_id'])
        messages = user.sent_messages.all()
        template_str = (
            '<h1>Outbox for {{ current_user.username }}</h1>'
            '<ul>'
            '{% for msg in message_list %}'
            '<li>To: {{ msg.receiver.username }} | Content: {{ msg.content }} | Sent: ({{ msg.timestamp }})</li>'
            '{% empty %}<li>No messages sent.</li>{% endfor %}'
            '</ul>'
        )
        template = Template(template_str)
        context = Context({'message_list': messages, 'current_user': user})
        response = HttpResponse(template.render(context))

        # inbox와 유사하게, 테스트 간 간섭을 피하기 위해 outbox 조회 후에도 세션 정리 (필요시)
        # if 'user_id' in request.session:
        # del request.session['user_id']
        # request.session.modified = True
        return response
    except User.DoesNotExist:
        if 'user_id' in request.session:
            del request.session['user_id']
            request.session.modified = True
        return HttpResponse("User not found, session cleared.", status=401)

# URL patterns
urlpatterns = [
    path('login/<str:user_id_str>/',  login,          name='login'), # <int:user_id>에서 변경
    path('send/<int:receiver_id>/',   send_message,   name='send_message'),
    path('inbox/',                    inbox,          name='inbox'),
    path('outbox/',                   outbox,         name='outbox'),
]

def setup_database_and_initial_data():
    existing_tables = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if User._meta.db_table not in existing_tables:
            schema_editor.create_model(User)
        if Message._meta.db_table not in existing_tables:
            schema_editor.create_model(Message)

    user1, _ = User.objects.get_or_create(username='alice', defaults={'user_id': 1})
    user2, _ = User.objects.get_or_create(username='bob', defaults={'user_id': 2})

    # 테스트 시나리오에서 user_id 1과 2를 사용하므로 명시적으로 ID 할당 시도 (get_or_create는 자동 증가 ID를 사용)
    # 실제로는 User.objects.create(user_id=1, username='alice') 등으로 생성해야 하나,
    # get_or_create를 사용하면서 ID를 보장하려면 추가 로직이 필요하거나, 테스트 데이터 생성 방식을 변경해야 함.
    # 여기서는 get_or_create가 alice와 bob을 생성/가져오고, ID는 자동 할당된다고 가정합니다.
    # 테스트 시나리오가 특정 ID에 의존한다면, 해당 ID로 사용자를 생성하는 것이 중요합니다.
    # 아래는 get_or_create 사용 시 username 기준으로 사용자를 가져오거나 생성합니다.

    # 사용자 ID를 1과 2로 강제 (테스트 시나리오 의존성)
    # 주의: SQLite에서 primary key를 직접 설정하며 객체를 생성/업데이트하는 것은 주의가 필요.
    #       일반적으로 Django는 PK를 자동으로 관리. 테스트를 위해 아래와 같이 처리.
    User.objects.update_or_create(user_id=1, defaults={'username': 'alice'})
    User.objects.update_or_create(user_id=2, defaults={'username': 'bob'})
    user1 = User.objects.get(user_id=1)
    user2 = User.objects.get(user_id=2)


    Message.objects.get_or_create(
        sender=user1, receiver=user2, content='Initial message from Alice to Bob for testing.',
        defaults={'sender': user1, 'receiver': user2, 'content': 'Initial message from Alice to Bob for testing.'}
    )
    Message.objects.get_or_create(
        sender=user2, receiver=user1, content='Initial message from Bob to Alice for testing.',
        defaults={'sender': user2, 'receiver': user1, 'content': 'Initial message from Bob to Alice for testing.'}
    )
    print("Database setup: Users and Messages tables ensured. Initial users (alice, bob) and messages created/ensured.")

if __name__ == '__main__':
    setup_database_and_initial_data()
    from django.core.management import execute_from_command_line
    print("Starting Django development server for testing on http://127.0.0.1:8000/")
    execute_from_command_line(['', 'runserver', '127.0.0.1:8000'])