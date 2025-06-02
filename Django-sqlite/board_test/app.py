from django.conf import settings
from django.db import models, connection
from django.core.management import execute_from_command_line
from django.template import Template, Context
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect

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
        request.session['user_id'] = user.user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse(status=200)
    return HttpResponse(status=404)

def create_post(request):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        user_id = request.session['user_id']
        user = User.objects.get(user_id=user_id)
        Post.objects.create(user=user, title=title, content=content)
    return redirect('view_posts')

def view_posts(request):
    posts = Post.objects.filter(is_deleted=False).all()
    html = """
    <html><body>
        <h1>Posts</h1>
        <ul>
    """
    for post in posts:
        html += f"<li><a href='/posts/{post.post_id}/'>{post.title}</a>"
        if request.session.get('user_id', None) is not None:
            html += f" | <a href='/posts/{post.post_id}/delete/'>Delete</a>"
        html += f"</li>"
    html += """
        </ul>
    </body></html>
    """
    return HttpResponse(html)

def post_detail(request, post_id):
    post = Post.objects.get(post_id=post_id)
    comments = Comment.objects.filter(post=post).all()
    user_id = request.session.get('user_id', None)
    if user_id is not None:
        user = User.objects.get(user_id=user_id)
        comment_form = """
        <form method="POST" action="{% url 'add_comment' post_id=post_id %}">
            {% csrf_token %}
            <textarea name="content"></textarea>
            <button type="submit">Add Comment</button>
        </form>
        """
    else:
        comment_form = ''
    html = f"""
    <html><body>
        <h1>{post.title}</h1>
        <p>{post.content}</p>
        <p>Created by: {post.user.username} | {post.created_at}</p>
        <h2>Comments ({len(comments)})</h2>
        <ul>
    """
    for comment in comments:
        html += f"<li>{comment.content} by {comment.user.username} | {comment.created_at}</li>"
    html += f"""
        </ul>
        {comment_form}
    </body></html>
    """
    return HttpResponse(html)

def add_comment(request, post_id):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    if request.method == 'POST':
        content = request.POST.get('content')
        user_id = request.session['user_id']
        user = User.objects.get(user_id=user_id)
        post = Post.objects.get(post_id=post_id)
        Comment.objects.create(user=user, post=post, content=content)
    return redirect('post_detail', post_id=post_id)

def delete_post(request, post_id):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    post = Post.objects.get(post_id=post_id)
    if post.user.user_id == request.session['user_id'] or request.session['is_admin']:
        post.is_deleted = True
        post.save()
    return redirect('view_posts')

from django.urls import path

urlpatterns = [
    path('login/<int:user_id>/',         login,        name='login'),
    path('posts/',                       view_posts,   name='view_posts'),
    path('posts/create/',                create_post,  name='create_post'),
    path('posts/<int:post_id>/',         post_detail,  name='post_detail'),
    path('posts/<int:post_id>/comment/', add_comment,  name='add_comment'),
    path('posts/<int:post_id>/delete/',  delete_post,  name='delete_post'),
]

if __name__ == '__main__':
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users'    not in existing: schema_editor.create_model(User)
        if 'posts'    not in existing: schema_editor.create_model(Post)
        if 'comments' not in existing: schema_editor.create_model(Comment)

    user1 = User.objects.create(username='user',  is_admin=False)
    admin = User.objects.create(username='admin', is_admin=True)

    post1 = Post.objects.create(user=user1, title='Hello World', content='This is the first post.')
    post2 = Post.objects.create(user=admin, title='Admin Notice', content='Please follow the rules.')

    Comment.objects.create(post=post1, user=admin, content='Welcome to the board!')
    Comment.objects.create(post=post2, user=user1, content='Got it, thank you!')

    execute_from_command_line(['', 'runserver'])