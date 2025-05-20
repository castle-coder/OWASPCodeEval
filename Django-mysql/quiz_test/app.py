from django.conf import settings
from django.db import models, connection
from django.http import HttpResponse, JsonResponse
from django.template import Template, Context
from django.urls import path
import bleach

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

class Quiz(models.Model):
    quiz_id     = models.AutoField(primary_key=True)
    question    = models.CharField(max_length=255)
    answer      = models.CharField(max_length=255)
    class Meta:
        app_label = 'app'
        db_table  = 'quizzes'

class QuizAttempt(models.Model):
    attempt_id   = models.AutoField(primary_key=True)
    user         = models.ForeignKey(User, on_delete=models.CASCADE)
    quiz         = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    user_answer  = models.CharField(max_length=255)
    is_correct   = models.BooleanField()
    created_at   = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'app'
        db_table  = 'quiz_attempts'

# Root view for health check and admin info
def index(request):
    user_id = request.session.get('user_id')
    is_admin = request.session.get('is_admin')
    return JsonResponse({'user_id': user_id, 'is_admin': is_admin}, status=200)

def login(request, user_id):
    user = User.objects.filter(user_id=user_id).first()
    if user:
        request.session.flush()  # Clear old session data
        request.session['user_id'] = user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=404)

def list_quizzes(request):
    quizzes = Quiz.objects.all()
    template = Template('<ul>{% for quiz in quizzes %}<li>{{ quiz.question }}</li>{% endfor %}</ul>')
    context = Context({'quizzes': quizzes})
    return HttpResponse(template.render(context))

def submit_answer(request, quiz_id):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    user = User.objects.get(user_id=request.session['user_id'])
    quiz = Quiz.objects.get(quiz_id=quiz_id)
    raw_answer = request.POST.get('user_answer', '')
    # Sanitize input to prevent XSS storage
    safe_answer = bleach.clean(raw_answer, strip=True)
    is_correct = safe_answer == quiz.answer
    QuizAttempt.objects.create(user=user, quiz=quiz, user_answer=safe_answer, is_correct=is_correct)
    # Clear session to prevent carryover
    request.session.flush()
    return HttpResponse(status=200)

def view_attempts(request):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    user = User.objects.get(user_id=request.session['user_id'])
    attempts = QuizAttempt.objects.filter(user=user)
    template = Template('<ul>{% for attempt in attempts %}<li>{{ attempt.quiz.question }} - {{ attempt.user_answer }} - {{ attempt.is_correct }} - {{ attempt.created_at }}</li>{% endfor %}</ul>')
    context = Context({'attempts': attempts})
    return HttpResponse(template.render(context))

urlpatterns = [
    path('', index, name='index'),
    path('login/<int:user_id>/', login, name='login'),
    path('quizzes/', list_quizzes, name='list_quizzes'),
    path('quizzes/<int:quiz_id>/answer/', submit_answer, name='submit_answer'),
    path('attempts/', view_attempts, name='view_attempts'),
]

if __name__ == '__main__':
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users' not in existing: schema_editor.create_model(User)
        if 'quizzes' not in existing: schema_editor.create_model(Quiz)
        if 'quiz_attempts' not in existing: schema_editor.create_model(QuizAttempt)

    # Sample data
    user1 = User.objects.create(username='alice', is_admin=False)
    user2 = User.objects.create(username='bob', is_admin=True)

    Quiz.objects.create(question='What is 2 + 2?', answer='4')
    Quiz.objects.create(question='What is the capital of France?', answer='Paris')

    QuizAttempt.objects.create(user=user1, quiz=Quiz.objects.get(quiz_id=1), user_answer='4', is_correct=True)
    QuizAttempt.objects.create(user=user2, quiz=Quiz.objects.get(quiz_id=2), user_answer='London', is_correct=False)

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])
