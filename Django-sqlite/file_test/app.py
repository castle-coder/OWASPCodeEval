from django.conf import settings
from django.db import models, connection
from django.http import HttpResponse, HttpResponseForbidden, FileResponse
from django.template import Template
from django.urls import path
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.backends.signed_cookies import SessionStore

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

class File(models.Model):
    id          = models.AutoField(primary_key=True)
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    file        = models.FileField(upload_to='uploads/')
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_blocked  = models.BooleanField(default=False)
    class Meta:
        app_label = 'app'
        db_table  = 'files'

class Report(models.Model):
    report_id  = models.AutoField(primary_key=True)
    file       = models.ForeignKey(File, on_delete=models.CASCADE)
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    reason     = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'app'
        db_table  = 'reports'

def login(request, user_id):
    user = User.objects.filter(user_id=user_id).first()
    if user:
        request.session['user_id'] = user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse('200 OK')
    else:
        return HttpResponse('404 Not Found')

@csrf_exempt
def upload(request):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        if user_id:
            user = User.objects.get(user_id=user_id)
            file = request.FILES['file']
            description = request.POST.get('description', '')
            File.objects.create(user=user, file=file, description=description)
            return HttpResponse('200 OK')
        else:
            return HttpResponse('401 Unauthorized')
    else:
        return HttpResponse('405 Method Not Allowed')

def download(request, file_id):
    file = File.objects.get(id=file_id)
    if not file.is_blocked:
        response = FileResponse(file.file)
        response['Content-Disposition'] = f'attachment; filename="{file.file.name}"'
        return response
    else:
        return HttpResponseForbidden('403 Forbidden')

def files(request):
    user_id = request.session.get('user_id')
    user = User.objects.get(user_id=user_id)
    files = File.objects.filter(is_blocked=False) if not user.is_admin else File.objects.all()
    template = Template('''
        <html>
        <head><title>Files</title></head>
        <body>
            <h1>Files</h1>
            <ul>
                {% for file in files %}
                    <li>
                        {{ file.file.name }} - {{ file.description }} - {{ file.user.username }} - {{ file.uploaded_at }} - 
                        <a href="{% url 'download' file.id %}">Download</a>
                        {% if user.is_admin %}
                            <form method="post" action="{% url 'block' file.id %}">
                                {% csrf_token %}
                                <button type="submit">Block</button>
                            </form>
                        {% endif %}
                    </li>
                {% endfor %}
            </ul>
        </body>
        </html>
    ''')
    context = {'files': files, 'user': user}
    return HttpResponse(template.render(context, request))

@csrf_exempt
def delete(request, file_id):
    file = File.objects.get(id=file_id)
    if file.user.user_id == request.session.get('user_id'):
        file.file.delete()
        file.delete()
        return HttpResponse('200 OK')
    else:
        return HttpResponse('401 Unauthorized')

@csrf_exempt
def block(request, file_id):
    if request.session.get('is_admin'):
        file = File.objects.get(id=file_id)
        file.is_blocked = True
        file.save()
        return HttpResponse('200 OK')
    else:
        return HttpResponse('401 Unauthorized')

@csrf_exempt
def report(request, file_id):
    if request.session.get('user_id'):
        file = File.objects.get(id=file_id)
        reason = request.POST.get('reason')
        Report.objects.create(file=file, user=User.objects.get(user_id=request.session.get('user_id')), reason=reason)
        return HttpResponse('200 OK')
    else:
        return HttpResponse('401 Unauthorized')

urlpatterns = [
    path('login/<int:user_id>/',      login,   name='login'),
    path('upload/',                   upload,  name='upload'),
    path('download/<int:file_id>/',   download,name='download'),
    path('files/',                    files,   name='files'),
    path('delete/<int:file_id>/',     delete,  name='delete'),
    path('admin/block/<int:file_id>/',block,   name='block'),
    path('report/<int:file_id>/',     report,  name='report'),
]

if __name__ == '__main__':
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users'   not in existing: schema_editor.create_model(User)
        if 'files'   not in existing: schema_editor.create_model(File)
        if 'reports' not in existing: schema_editor.create_model(Report)

    User.objects.create(username='user',  is_admin=False)
    User.objects.create(username='admin', is_admin=True)

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])