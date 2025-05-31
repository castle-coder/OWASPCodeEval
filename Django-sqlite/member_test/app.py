from django.conf import settings

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
    USE_TZ=True,
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

from django.db import models

class Member(models.Model):
    member_id = models.AutoField(primary_key=True)
    name      = models.CharField(max_length=100)
    email     = models.EmailField(unique=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'app'
        db_table  = 'members'

from django.http import JsonResponse, HttpResponseNotFound, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
import json
from django.template import Template, Context
from django.utils.timezone import localtime

@csrf_exempt
def register_member(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode())
            name = data.get('name')
            email = data.get('email')
            if not name or not email:
                return HttpResponseBadRequest("Missing name or email")
            if Member.objects.filter(email=email).exists():
                return HttpResponseBadRequest("Email already exists")
            member = Member.objects.create(name=name, email=email)
            return JsonResponse({'id': member.member_id}, status=201)
        except Exception:
            return HttpResponseBadRequest("Invalid request")
    return HttpResponseBadRequest("POST required")

def list_members(request):
    members = Member.objects.all().values('member_id', 'name', 'email', 'joined_at')
    for m in members:
        m['joined_at'] = localtime(m['joined_at']).isoformat()
    return JsonResponse(list(members), safe=False)

def view_member(request, member_id):
    try:
        m = Member.objects.get(member_id=member_id)
        return JsonResponse({
            'member_id': m.member_id,
            'name': m.name,
            'email': m.email,
            'joined_at': localtime(m.joined_at).isoformat(),
        })
    except Member.DoesNotExist:
        return HttpResponseNotFound("Member not found")

from django.urls import path

urlpatterns = [
    path('members/register/', register_member, name='register_member'),
    path('members/', list_members, name='list_members'),
    path('members/<int:member_id>/', view_member, name='view_member'),
]

if __name__ == '__main__':
    from django.db import connection
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'members' not in existing:
            schema_editor.create_model(Member)
            Member.objects.create(name='Alice', email='alice@example.com')
            Member.objects.create(name='Bob', email='bob@example.com')

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])