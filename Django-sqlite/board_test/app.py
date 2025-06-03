from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.template import Template, Context
from django.db import models, connection
from django.urls import path
from django.views.decorators.http import require_GET, require_POST

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

@require_GET
def login(request, user_id):
    user = User.objects.filter(user_id=user_id).first()
    if user:
        request.session['user_id'] = user.user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=404)

@require_POST
def create_post(request):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    user = User.objects.get(user_id=request.session['user_id'])
    title = request.POST.get('title')
    content = request.POST.get('content')
    if title and content:
        Post.objects.create(user=user, title=title, content=content)
        return HttpResponse(status=201)
    else:
        return HttpResponse(status=400)

@require_GET
def view_posts(request):
    posts = Post.objects.filter(is_deleted=False).order_by('-created_at')
    template = Template("""
        <ul>
        {% for post in posts %}
            <li><a href="{% url 'post_detail' post.post_id %}">{{ post.title }} ({{ post.created_at }}) ({{ post.comments.count }} comments)</a>
            {% if request.session.is_admin or post.user_id == request.session.user_id %}
                <form action="{% url 'delete_post' post.post_id %}" method="post">
                    <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
                    <button type="submit">Delete</button>
                </form>
            {% endif %}
            </li>
        {% endfor %}
        </ul>
    """)
    context = Context({'posts': posts})
    return HttpResponse(template.render(context))

@require_GET
def post_detail(request, post_id):
    post = Post.objects.get(post_id=post_id)
    comments = post.comments.all()
    template = Template("""
        <h1>{{ post.title }}</h1>
        <p>{{ post.content }}</p>
        <h2>Comments</h2>
        <ul>
        {% for comment in comments %}
            <li>{{ comment.content }} ({{ comment.created_at }})</li>
        {% endfor %}
        </ul>
        {% if request.session.user_id %}
            <form action="{% url 'add_comment' post.post_id %}" method="post">
                <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
                <textarea name="content"></textarea>
                <button type="submit">Add Comment</button>
            </form>
        {% endif %}
    """)
    context = Context({'post': post, 'comments': comments})
    return HttpResponse(template.render(context))

@require_POST
def add_comment(request, post_id):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    user = User.objects.get(user_id=request.session['user_id'])
    content = request.POST.get('content')
    if content:
        Comment.objects.create(post_id=post_id, user=user, content=content)
        return HttpResponse(status=201)
    else:
        return HttpResponse(status=400)

@require_POST
def delete_post(request, post_id):
    if 'user_id' not in request.session:
        return HttpResponse(status=401)
    post = Post.objects.get(post_id=post_id)
    if post.user_id == request.session['user_id'] or request.session['is_admin']:
        post.is_deleted = True
        post.save()
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=403)

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

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])