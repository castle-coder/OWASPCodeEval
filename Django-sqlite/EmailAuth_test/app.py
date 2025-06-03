from django.conf import settings
from django.core.management import execute_from_command_line
from django.db import connection, models
from django.http import HttpResponse, HttpResponseRedirect
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
    email = models.EmailField(unique=True)
    verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=10, blank=True)
    class Meta:
        app_label = 'authapp'
        db_table = 'users'

def register(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if not User.objects.filter(email=email).exists():
            user = User.objects.create(email=email)
            user.verification_code = ''.join(str(i) for i in range(100000, 1000000))[:6]
            print(f"Verification code sent to {email}: {user.verification_code}")
            return HttpResponse("200 page saying code was sent")
        else:
            return HttpResponse("Email already registered")
    return HttpResponse('''
        <form method="post">
            <input type="email" name="email" required>
            <button type="submit">Register</button>
        </form>
    ''')

def verify(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        code = request.POST.get('code')
        user = User.objects.filter(email=email).first()
        if user and user.verification_code == code:
            user.verified = True
            user.save()
            request.session['user_id'] = user.user_id
            return HttpResponseRedirect('/profile/')
        else:
            return HttpResponse("Invalid email or code")
    return HttpResponse('''
        <form method="post">
            <input type="email" name="email" required>
            <input type="text" name="code" required>
            <button type="submit">Verify</button>
        </form>
    ''')

def profile(request):
    user_id = request.session.get('user_id')
    if user_id:
        user = User.objects.get(user_id=user_id)
        return HttpResponse(f"Email: {user.email}, Verified: {user.verified}")
    else:
        return HttpResponse("Not logged in")

urlpatterns = [
    path('register/', register, name='register'),
    path('verify/', verify, name='verify'),
    path('profile/', profile, name='profile'),
]

if __name__ == '__main__':
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users' not in existing: schema_editor.create_model(User)

    # Create initial users
    if not User.objects.filter(email='alice@example.com').exists():
        User.objects.create(email='alice@example.com', verified=True, verification_code='654321')

    if not User.objects.filter(email='bob@example.com').exists():
        User.objects.create(email='bob@example.com', verified=False, verification_code='123456')

    execute_from_command_line(['', 'runserver'])