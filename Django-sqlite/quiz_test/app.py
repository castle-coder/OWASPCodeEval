from django.conf import settings
from django.db import models, connection
from django.http import HttpResponse, JsonResponse
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

def login(request, user_id):
    user = User.objects.filter(user_id=user_id).first()
    if user:
        request.session['user_id'] = user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=404)

def list_quizzes(request):
    quizzes = Quiz.objects.all()
    return JsonResponse([{'quiz_id': q.quiz_id, 'question': q.question} for q in quizzes], safe=False)

def submit_answer(request, quiz_id):
    user_id = request.session.get('user_id')
    if user_id is None:
        return HttpResponse(status=403)

    quiz = Quiz.objects.filter(quiz_id=quiz_id).first()
    if not quiz:
        return HttpResponse(status=404)

    user_answer = request.POST.get('user_answer')
    is_correct = user_answer == quiz.answer
    QuizAttempt.objects.create(user_id=user_id, quiz_id=quiz_id, user_answer=user_answer, is_correct=is_correct)
    return HttpResponse(status=200)

def view_attempts(request):
    user_id = request.session.get('user_id')
    if user_id is None:
        return HttpResponse(status=403)

    attempts = QuizAttempt.objects.filter(user_id=user_id)
    return JsonResponse([
        {
            'quiz_id': a.quiz_id,
            'question': a.quiz.question,
            'user_answer': a.user_answer,
            'is_correct': a.is_correct,
            'created_at': a.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        for a in attempts
    ], safe=False)

urlpatterns = [
    path('login/<int:user_id>/', login, name='login'),
    path('quizzes/', list_quizzes, name='list_quizzes'),
    path('quizzes/<int:quiz_id>/answer/', submit_answer, name='submit_answer'),
    path('attempts/', view_attempts, name='view_attempts'),
]

if __name__ == '__main__':
    from django.db import connection

    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users' not in existing: schema_editor.create_model(User)
        if 'quizzes' not in existing: schema_editor.create_model(Quiz)
        if 'quiz_attempts' not in existing: schema_editor.create_model(QuizAttempt)

    user1 = User.objects.create(username='alice', is_admin=False)
    user2 = User.objects.create(username='bob', is_admin=True)

    Quiz.objects.create(question='What is 2 + 2?', answer='4')
    Quiz.objects.create(question='What is the capital of France?', answer='Paris')

    QuizAttempt.objects.create(user=user1, quiz=Quiz.objects.get(quiz_id=1), user_answer='4', is_correct=True)
    QuizAttempt.objects.create(user=user2, quiz=Quiz.objects.get(quiz_id=2), user_answer='London', is_correct=False)

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])