from django.conf import settings
from django.db import models
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
            user = User.objects.create(email=email, verification_code='123456')
            print(f"Verification code sent to {email}: {user.verification_code}")
            return JsonResponse({'message': 'Code sent'})
        else:
            return JsonResponse({'error': 'Email already registered'}, status=400)
    return HttpResponse('''
        <form method="post">
            Email: <input type="email" name="email"><br>
            <input type="submit" value="Register">
        </form>
    ''')

def verify(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        code = request.POST.get('code')
        user = User.objects.filter(email=email, verification_code=code).first()
        if user:
            user.verified = True
            user.save()
            request.session['user_id'] = user.user_id
            return JsonResponse({'message': 'User verified.'})
        else:
            return JsonResponse({'error': 'Invalid code'}, status=400)
    return HttpResponse('''
        <form method="post">
            Email: <input type="email" name="email"><br>
            Verification Code: <input type="text" name="code"><br>
            <input type="submit" value="Verify">
        </form>
    ''')

def profile(request):
    if 'user_id' in request.session:
        user = User.objects.get(user_id=request.session['user_id'])
        return HttpResponse(f'''
            Email: {user.email}<br>
            Verified: {user.verified}
        ''')
    else:
        return HttpResponse('Please log in first', status=401)

urlpatterns = [
    path('register/', register, name='register'),
    path('verify/', verify, name='verify'),
    path('profile/', profile, name='profile'),
]

if __name__ == '__main__':
    from django.db import connection
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users' not in existing: schema_editor.create_model(User)

    # Create initial users
    if not User.objects.filter(email='alice@example.com').exists():
        User.objects.create(email='alice@example.com', verified=True, verification_code='654321')

    if not User.objects.filter(email='bob@example.com').exists():
        User.objects.create(email='bob@example.com', verified=False, verification_code='123456')

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])