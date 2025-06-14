from django.conf import settings
from django.db import models
from django.http import HttpResponse, HttpResponseNotFound
from django.template import Template, Context
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import JsonResponse
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

class Post(models.Model):
    post_id     = models.AutoField(primary_key=True)
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    title       = models.CharField(max_length=200)
    content     = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    is_deleted  = models.BooleanField(default=False)
    class Meta:
        app_label = 'app'
        db_table  = 'posts'

class Comment(models.Model):
    comment_id  = models.AutoField(primary_key=True)
    post        = models.ForeignKey(Post, on_delete=models.CASCADE)
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    content     = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'app'
        db_table  = 'comments'

def login(request, user_id):
    user = User.objects.filter(user_id=user_id).first()
    if user:
        request.session['user_id'] = user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse('200 OK')
    else:
        return HttpResponseNotFound('404 Not Found')

def view_posts(request):
    posts = Post.objects.filter(is_deleted=False).values('post_id', 'title', 'user__username', 'created_at')
    html = '<ul>'
    for post in posts:
        html += f'<li>{post["title"]} by {post["user__username"]} - {post["created_at"]}</li>'
    html += '</ul>'
    return HttpResponse(html)

def search_posts(request):
    keyword = request.GET.get('q', '')
    posts = Post.objects.filter(is_deleted=False, title__icontains=keyword) | Post.objects.filter(is_deleted=False, content__icontains=keyword)
    html = '<ul>'
    for post in posts:
        html += f'<li><a href="/posts/{post.post_id}/">{post.title}</a></li>'
    html += '</ul>'
    return HttpResponse(html)

@csrf_exempt
def add_comment(request, post_id):
    if request.session.get('user_id') is None:
        return JsonResponse({'error': 'Not logged in'}, status=401)
    user = User.objects.get(user_id=request.session['user_id'])
    post = Post.objects.get(post_id=post_id)
    if request.method == 'POST':
        content = request.POST.get('content', '')
        Comment.objects.create(post=post, user=user, content=content)
        return JsonResponse({'message': 'Comment added'}, status=200)
    else:
        return HttpResponse('Method not allowed', status=405)

urlpatterns = [
    path('login/<int:user_id>/', login, name='login'),
    path('posts/', view_posts, name='view_posts'),
    path('search/', search_posts, name='search_posts'),
    path('posts/<int:post_id>/comment/', add_comment, name='add_comment'),
]

from django.db import connection

existing = connection.introspection.table_names()
with connection.schema_editor() as schema_editor:
    if 'users'    not in existing: schema_editor.create_model(User)
    if 'posts'    not in existing: schema_editor.create_model(Post)
    if 'comments' not in existing: schema_editor.create_model(Comment)

user1 = User.objects.create(username='alice', is_admin=False)
user2 = User.objects.create(username='bob', is_admin=True)

post1 = Post.objects.create(user=user1, title='Django Tips', content='Learn how to use Django effectively.')
post2 = Post.objects.create(user=user2, title='Board Rules', content='Please be respectful.')

Comment.objects.create(post=post1, user=user2, content='Great post!')

from django.core.management import execute_from_command_line
execute_from_command_line(['', 'runserver'])