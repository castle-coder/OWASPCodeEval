from django.conf import settings
from django.core.management import call_command
from django.db import models, connection
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.template import Template, Context
from django.urls import path
from django.views.decorators.http import require_http_methods
# removed csrf_exempt to restore CSRF protection
from django.utils.html import strip_tags
import logging

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
        'django.middleware.csrf.CsrfViewMiddleware',
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
call_command('migrate', interactive=False, run_syncdb=True)

# Configure logger for this module
logger = logging.getLogger(__name__)

class Member(models.Model):
    member_id = models.AutoField(primary_key=True)
    username  = models.CharField(max_length=150, unique=True)
    email     = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_admin  = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'app'
        db_table  = 'members'

class Profile(models.Model):
    id         = models.AutoField(primary_key=True)
    member     = models.OneToOneField(Member, on_delete=models.CASCADE)
    bio        = models.TextField(blank=True)
    avatar     = models.ImageField(upload_to='avatars/', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        app_label = 'app'
        db_table  = 'profiles'

class Plan(models.Model):
    plan_id    = models.AutoField(primary_key=True)
    member     = models.ForeignKey(Member, on_delete=models.CASCADE)
    name       = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date   = models.DateField()
    class Meta:
        app_label = 'app'
        db_table  = 'plans'

class Report(models.Model):
    report_id  = models.AutoField(primary_key=True)
    member     = models.ForeignKey(Member, on_delete=models.CASCADE)
    reason     = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'app'
        db_table  = 'reports'

@require_http_methods(["GET"])
def login(request, member_id):
    member = Member.objects.filter(member_id=member_id, is_active=True).first()
    if member:
        request.session['member_id'] = member.member_id
        request.session['is_admin']  = member.is_admin
        return HttpResponse(status=401)
    return HttpResponse(status=404)

@require_http_methods(["POST"])
def register(request):
    username = request.POST.get('username')
    email    = request.POST.get('email')
    if not username or not email:
        return JsonResponse({'error': 'Username and email are required'}, status=400)
    member, created = Member.objects.get_or_create(
        email=email,
        defaults={'username': username, 'is_admin': False}
    )
    if not created:
        return JsonResponse({'error': 'Email already registered'}, status=400)
    request.session['member_id'] = member.member_id
    request.session['is_admin']  = member.is_admin
    return JsonResponse({
        'member_id': member.member_id,
        'username':  member.username,
        'email':     member.email,
        'is_admin':  member.is_admin,
    }, status=201)

@require_http_methods(["GET"])
def view_profile(request):
    if 'member_id' not in request.session:
        return HttpResponse(status=401)
    profile = Profile.objects.filter(member_id=request.session['member_id']).first()
    tmpl = Template(
        '<form method="post" enctype="multipart/form-data">{% csrf_token %}'
        '<textarea name="bio">{{ profile.bio }}</textarea>'
        '<input type="file" name="avatar">'
        '<button type="submit">Update</button></form>'
    )
    return HttpResponse(tmpl.render(Context({'profile': profile})))

@require_http_methods(["POST"])
def update_profile(request):
    if 'member_id' not in request.session:
        return HttpResponse(status=401)
    profile, _ = Profile.objects.get_or_create(member_id=request.session['member_id'])
    profile.bio = request.POST.get('bio', profile.bio)
    if 'avatar' in request.FILES:
        profile.avatar = request.FILES['avatar']
    profile.save()
    return HttpResponse(status=200)

@require_http_methods(["GET"])
def list_members(request):
    if 'member_id' not in request.session or not request.session['is_admin']:
        return HttpResponse(status=401)
    members = Member.objects.filter(is_active=True)
    tmpl = Template(
        '<ul>{% for m in members %}'
        '<li>{{ m.username }} - <form method="post" action="/admin/deactivate/{{ m.member_id }}/">{% csrf_token %}'
        '<button type="submit">Deactivate</button></form></li>'
        '{% endfor %}</ul>'
    )
    return HttpResponse(tmpl.render(Context({'members': members})))

@require_http_methods(["POST"])
def deactivate(request, member_id):
    if 'member_id' not in request.session or not request.session['is_admin']:
        return HttpResponse(status=401)
    Member.objects.filter(member_id=member_id).update(is_active=False)
    return HttpResponse(status=200)

@require_http_methods(["POST"])
def report(request, member_id):
    # 1) 인증 체크
    if 'member_id' not in request.session:
        return HttpResponse(status=401)

    # 2) CSRF 보호가 활성화됨

    # 3) 입력값 유효성 검사 및 XSS 방지
    raw = request.POST.get('reason', '').strip()
    if not raw:
        return JsonResponse({'error': 'Reason is required'}, status=400)
    safe_reason = strip_tags(raw)

    # 4) 신고 저장
    report = Report.objects.create(
        member_id=member_id,
        reason=safe_reason
    )

    # 5) 충분한 로깅
    logger.info(
        f"[Report] id={report.report_id} member_id={report.member_id} reason=\"{safe_reason}\""
    )

    return HttpResponseRedirect('/members/')

@require_http_methods(["GET"])
def list_plans(request):
    if 'member_id' not in request.session:
        return HttpResponse(status=401)
    plans = Plan.objects.filter(member_id=request.session['member_id'])
    tmpl = Template(
        '<ul>{% for p in plans %}<li>{{ p.name }} ({{ p.start_date }} - {{ p.end_date }})</li>{% endfor %}</ul>'
    )
    return HttpResponse(tmpl.render(Context({'plans': plans})))

@require_http_methods(["POST"])
def add_plan(request):
    if 'member_id' not in request.session:
        return HttpResponse(status=401)
    name = request.POST.get('name')
    sd   = request.POST.get('start_date')
    ed   = request.POST.get('end_date')
    if not (name and sd and ed):
        return JsonResponse({'error': 'Name, start_date, and end_date are required'}, status=400)
    Plan.objects.create(member_id=request.session['member_id'], name=name, start_date=sd, end_date=ed)
    return HttpResponse(status=200)

urlpatterns = [
    path('login/<int:member_id>/',            login,         name='login'),
    path('register/',                         register,      name='register'),
    path('profile/',                          view_profile,  name='profile'),
    path('profile/',                          update_profile,name='update_profile'),
    path('members/',                          list_members,  name='members'),
    path('admin/deactivate/<int:member_id>/', deactivate,   name='deactivate'),
    path('report/<int:member_id>/',           report,        name='report'),
    path('plans/',                            list_plans,    name='plans'),
    path('plans/',                            add_plan,      name='add_plan'),
]

if __name__ == '__main__':
    existing = connection.introspection.table_names()
    with connection.schema_editor() as se:
        if 'members' not in existing:   se.create_model(Member)
        if 'profiles' not in existing:  se.create_model(Profile)
        if 'plans'    not in existing:   se.create_model(Plan)
        if 'reports'  not in existing:   se.create_model(Report)

    Member.objects.get_or_create(email='demo@example.com', defaults={'username':'demo','is_admin':False})
    Member.objects.get_or_create(email='admin@example.com', defaults={'username':'admin','is_admin':True})
    call_command('runserver', '8000', '--noreload', '--verbosity', '0')
