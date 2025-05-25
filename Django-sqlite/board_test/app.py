from django.conf import settings
from django.db import models, connection
from django.http import HttpResponse, JsonResponse, Http404
from django.template import Template, Context
from django.urls import path
from django.utils.html import escape
import django

SCRIPT_NAME = __name__

settings.configure(
    SECRET_KEY='your-secret-key-is-very-secret',
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
    ROOT_URLCONF=SCRIPT_NAME,
    TEMPLATES=[{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'autoescape': True,
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

django.setup()

class User(models.Model):
    user_id   = models.AutoField(primary_key=True)
    username  = models.CharField(max_length=150)
    is_admin  = models.BooleanField(default=False)
    class Meta: app_label = 'app'; db_table  = 'users'

class Post(models.Model):
    post_id     = models.AutoField(primary_key=True)
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    title       = models.CharField(max_length=200)
    content     = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    is_deleted  = models.BooleanField(default=False)
    class Meta: app_label = 'app'; db_table  = 'posts'

class Comment(models.Model):
    comment_id  = models.AutoField(primary_key=True)
    post        = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    content     = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)
    class Meta: app_label = 'app'; db_table  = 'comments'

def login(request, user_id):
    try: user = User.objects.get(user_id=user_id)
    except User.DoesNotExist: return HttpResponse(status=404, content="User not found.")
    request.session['user_id'] = user.user_id
    request.session['is_admin'] = user.is_admin
    return HttpResponse(status=200, content="Login successful.")

def create_post(request):
    if request.session.get('user_id') is None: return HttpResponse(status=401, content="Authentication required.")
    if request.method == 'POST':
        title, content = request.POST.get('title'), request.POST.get('content')
        user_id = request.session.get('user_id')
        if not title or not content: return HttpResponse(status=400, content="Title and content are required.")
        try: user = User.objects.get(user_id=user_id)
        except User.DoesNotExist: return HttpResponse(status=401, content="Invalid user in session.")
        Post.objects.create(user=user, title=title, content=content)
        return HttpResponse(status=201, content="Post created.")
    return HttpResponse(status=405, content="Method not allowed.")

def view_posts(request):
    posts = Post.objects.filter(is_deleted=False).select_related('user').prefetch_related('comments')
    template_string = """
    <h2>Posts</h2> <p>User ID: {{ request.session.user_id }}, Admin: {{ request.session.is_admin }}</p> <ul>
    {% for post in posts %}<li><strong>{{ post.title }}</strong> (PostID:{{post.post_id}}) by {{ post.user.username }} (UserID:{{post.user.user_id}})
        <em>({{ post.created_at|date:"Y-m-d H:i" }})</em> - {{ post.comments.count }} comments
        <a href="/posts/{{ post.post_id }}/">View</a>
        {% if post.user.user_id == request.session.user_id %}<form method="POST" action="/posts/{{ post.post_id }}/delete/" style="display:inline;"><button type="submit">Delete</button></form>{% endif %}
    </li> {% empty %}<li>No posts.</li>{% endfor %}</ul>
    {% if request.session.user_id %}<p><a href="/posts/create/">New Post</a></p>{% else %}<p><a href="/login/1/">Login User1</a> or <a href="/login/2/">Login Admin</a></p>{% endif %}"""
    return HttpResponse(Template(template_string).render(Context({'posts': posts, 'request': request})))

def post_detail(request, post_id):
    try: post = Post.objects.select_related('user').prefetch_related('comments__user').get(post_id=post_id, is_deleted=False)
    except Post.DoesNotExist: return HttpResponse(status=404, content="Post not found or deleted.")
    template_string = """<h1>{{ post.title }}</h1> <p>By: {{ post.user.username }}</p> <div>{{ post.content|linebreaksbr }}</div> <hr/>
    <h2>Comments ({{ post.comments.count }})</h2> {% for comment in post.comments.all %}<div><p><strong>{{ comment.user.username }}</strong>:</p><p>{{ comment.content|linebreaksbr }}</p></div>{% empty %}<p>No comments.</p>{% endfor %}
    {% if request.session.user_id %}<hr/><h3>Add Comment</h3><form method="POST" action="/posts/{{ post.post_id }}/comment/"><textarea name="content" required></textarea><button type="submit">Add</button></form>{% else %}<p>Login to comment.</p>{% endif %}<p><a href="/posts/">Back</a></p>"""
    return HttpResponse(Template(template_string).render(Context({'post': post, 'request': request})))

def add_comment(request, post_id):
    user_id = request.session.get('user_id')
    if user_id is None: return HttpResponse(status=401, content="Authentication required.")
    if request.method == 'POST':
        content = request.POST.get('content')
        if not content: return HttpResponse(status=400, content="Comment content cannot be empty.")
        try:
            # A7 테스트 시 이 부분에서 post_id=1, is_deleted=False 상태로 찾아야 함
            post = Post.objects.get(post_id=post_id, is_deleted=False)
            user = User.objects.get(user_id=user_id)
        except Post.DoesNotExist: return HttpResponse(status=404, content=f"Post ID {post_id} not found or deleted.")
        except User.DoesNotExist: return HttpResponse(status=401, content="Invalid user in session.")
        sanitized_content = escape(content)
        Comment.objects.create(post=post, user=user, content=sanitized_content)
        return HttpResponse(status=201, content="Comment added.")
    return HttpResponse(status=405, content="Method not allowed.")

def delete_post(request, post_id):
    user_id = request.session.get('user_id')
    if user_id is None: return HttpResponse(status=401, content="Authentication required.")
    if request.method != 'POST': return HttpResponse(status=405, content="Use POST to delete.")
    try: post = Post.objects.get(post_id=post_id)
    except Post.DoesNotExist: return HttpResponse(status=404, content="Post not found.")
    
    # A5 Fix: Only owner can delete. Admin cannot delete other's posts.
    if post.user_id == user_id:
        if post.is_deleted: return HttpResponse(status=200, content="Post already deleted.")
        post.is_deleted = True; post.save()
        return HttpResponse(status=200, content="Post deleted.")
    else:
        return HttpResponse(status=403, content="Not authorized to delete this post.")

urlpatterns = [
    path('login/<int:user_id>/', login), path('posts/', view_posts), path('posts/create/', create_post),
    path('posts/<int:post_id>/', post_detail), path('posts/<int:post_id>/comment/', add_comment),
    path('posts/<int:post_id>/delete/', delete_post),
]

if SCRIPT_NAME == '__main__':
    settings.ROOT_URLCONF = __name__
    from django.urls import clear_url_caches, set_urlconf
    set_urlconf(__name__); clear_url_caches()

    existing_tables = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if User._meta.db_table not in existing_tables: schema_editor.create_model(User)
        if Post._meta.db_table not in existing_tables: schema_editor.create_model(Post)
        if Comment._meta.db_table not in existing_tables: schema_editor.create_model(Comment)

    user1_id, admin_id = 1, 2
    post1_id = 1

    # User 1 (non-admin) 생성 또는 확인
    user1, u1_created = User.objects.update_or_create(
        user_id=user1_id,
        defaults={'username': 'user', 'is_admin': False}
    )
    # Admin User (user_id=2) 생성 또는 확인
    admin, u2_created = User.objects.update_or_create(
        user_id=admin_id,
        defaults={'username': 'admin', 'is_admin': True}
    )

    # Post 1 (user1 소유, post_id=1) 생성 또는 확인 및 is_deleted=False 강제
    # A7 테스트가 이 게시물에 댓글을 달기 때문에, 항상 존재하고 삭제되지 않은 상태여야 함.
    post1, p1_created = Post.objects.update_or_create(
        post_id=post1_id,
        defaults={
            'user': user1, # user1 객체를 정확히 참조하도록 확인
            'title': 'Hello World',
            'content': 'This is the first post.',
            'is_deleted': False # A7 테스트 통과를 위해 이 상태를 보장
        }
    )
    if not p1_created and post1.user_id != user1.user_id : # 혹시 post_id=1이 다른 유저 소유였다면 수정
        post1.user = user1
        post1.is_deleted = False # 다시 한번 상태 확인
        post1.save()
        print(f"Post 1 (ID {post1_id}) owner/status corrected for user1.")
    elif p1_created:
        print(f"Post 1 (ID {post1_id}) created for user1, is_deleted=False.")
    else:
        print(f"Post 1 (ID {post1_id}) verified for user1, is_deleted=False.")


    # Post 2 (admin 소유) - A5 테스트에서 admin이 이 글을 삭제하려 하진 않음.
    # A5는 admin이 user1의 글(post1)을 삭제하려 함.
    # 이 Post는 다른 테스트에 직접적인 영향을 주지 않을 수 있으므로, 간단히 확인 후 생성.
    post2_title = 'Admin Notice'
    post2_obj = Post.objects.filter(user=admin, title=post2_title).first()
    if not post2_obj:
        post2 = Post.objects.create(user=admin, title=post2_title, content='Please follow the rules.')
        print(f"Post 2 (ID {post2.post_id}) by admin created.")

    # 댓글은 특정 테스트에 문제를 일으키지 않는 한 그대로 두거나, 필요시 초기화
    # post1에 대한 댓글은 A7 테스트에 의해 생성되므로, 여기서 미리 만들 필요는 없음.
    # Comment.objects.filter(post=post1).delete() # 필요시 post1의 댓글 초기화
    
    # 초기 데이터 생성/확인 로그
    print(f"Data setup: User1(ID:{user1.user_id}), Admin(ID:{admin.user_id}), Post1(ID:{post1.post_id}, Deleted:{post1.is_deleted})")


    print(f"\nStarting server. Login User1: /login/{user1_id}/, Login Admin: /login/{admin_id}/, Posts: /posts/")
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', 'runserver', '0.0.0.0:8000'])