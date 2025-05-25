import logging
import bleach
from django.conf import settings
from django.db import models, connection
from django.http import HttpResponse # JsonResponse는 현재 사용되지 않음
from django.template import Template, Context
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

# 로거 설정
logger = logging.getLogger(__name__) # __name__ 사용
handler = logging.StreamHandler()
# 로그 포맷에 파일명과 라인번호 추가
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s [%(name)s] %(filename)s:%(lineno)d %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO) # 기본 로그 레벨

settings.configure(
    SECRET_KEY='your-secret-key', # 실제 운영에서는 강력한 무작위 키 사용
    DEBUG=True, # 운영 환경에서는 False로 설정
    ALLOWED_HOSTS=['*'], # 운영 환경에서는 특정 호스트만 허용
    SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
    INSTALLED_APPS=[
        'django.contrib.contenttypes',
        'django.contrib.auth',
        'django.contrib.sessions',
        # 이 단일 파일 예제에서는 app_label을 모델에 명시하므로 INSTALLED_APPS에 'app'을 추가하지 않아도 동작 가능.
        # 일반적인 Django 프로젝트에서는 앱을 등록합니다.
    ],
    MIDDLEWARE=[
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        # CSRF 미들웨어는 기본적으로 활성화하는 것이 좋으나, 예제에서는 @csrf_exempt를 사용 중
        # 'django.middleware.csrf.CsrfViewMiddleware',
    ],
    ROOT_URLCONF=__name__, # __name__ 사용
    TEMPLATES=[{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages', # 필요시 메시지 프레임워크 사용
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

# Models
class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True) # username은 고유해야 함
    is_admin = models.BooleanField(default=False)

    class Meta:
        app_label = 'app'
        db_table = 'users'

    def __str__(self):
        return self.username

class Post(models.Model):
    post_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        app_label = 'app'
        db_table = 'posts'
        ordering = ['-created_at'] # 기본 정렬 순서 지정

    def __str__(self):
        return self.title

class Comment(models.Model):
    comment_id = models.AutoField(primary_key=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField() # 정제된 내용이 저장됨
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'app'
        db_table = 'comments'
        ordering = ['created_at'] # 댓글은 시간순으로 정렬

    def __str__(self):
        return f"Comment by {self.user.username} on {self.post.title}"

# Views
@csrf_exempt # 실제 서비스에서는 CSRF 보호를 적용하는 것이 원칙
def login(request, user_id):
    try:
        user = User.objects.get(user_id=user_id)
        request.session['user_id'] = user.user_id
        request.session['is_admin'] = user.is_admin
        logger.info(
            "User '%s' (ID: %s, Admin: %s) logged in. IP: %s",
            user.username, user.user_id, user.is_admin, request.META.get('REMOTE_ADDR')
        )
        return HttpResponse(status=200)
    except User.DoesNotExist:
        logger.warning(
            "Login attempt failed for non-existent user_id: %s. IP: %s",
            user_id, request.META.get('REMOTE_ADDR')
        )
        return HttpResponse(status=404)

def view_posts(request):
    posts = Post.objects.filter(is_deleted=False) # ordering은 모델 Meta에 정의됨
    template_string = """
    <h1>Posts</h1>
    {% for post in posts %}
        <div>
            <h2>{{ post.title }}</h2>
            <p>by {{ post.user.username }} ({{ post.created_at }})</p>
            <div>{{ post.content }}</div> {# Django 템플릿은 기본적으로 자동 이스케이프 #}
            <h4>Comments:</h4>
            {% for c in post.comment_set.all %}
                <p><b>{{ c.user.username }}:</b> {{ c.content }}</p> {# 댓글 내용도 자동 이스케이프 #}
            {% empty %}
                <p>No comments yet.</p>
            {% endfor %}
            <hr>
        </div>
    {% endfor %}
    """
    template = Template(template_string)
    context = Context({'posts': posts})
    return HttpResponse(template.render(context))

def search_posts(request):
    keyword = request.GET.get('q', '')
    # Q 객체를 사용하여 복잡한 쿼리 표현 가능
    from django.db.models import Q
    posts = Post.objects.filter(
        Q(is_deleted=False) & (Q(title__icontains=keyword) | Q(content__icontains=keyword))
    ).distinct()
    
    template_string = '{% for post in posts %}{{ post.title }} by {{ post.user.username }} ({{ post.created_at }})<br>{% endfor %}'
    template = Template(template_string)
    context = Context({'posts': posts})
    return HttpResponse(template.render(context))

@csrf_exempt # 실제 서비스에서는 CSRF 보호 적용
def add_comment(request, post_id):
    user_id_from_session = request.session.get('user_id')
    client_ip = request.META.get('REMOTE_ADDR')

    if not user_id_from_session:
        logger.warning(
            "Unauthorized attempt to add comment: No user_id in session. IP: %s, Post ID: %s",
            client_ip, post_id
        )
        return HttpResponse(status=401)

    try:
        # 삭제되지 않은 게시물에만 댓글 작성 가능
        post = Post.objects.get(post_id=post_id, is_deleted=False)
        user = User.objects.get(user_id=user_id_from_session)
    except Post.DoesNotExist:
        logger.warning(
            "Attempt to comment on non-existent or deleted post. Post ID: %s, User ID: %s, IP: %s",
            post_id, user_id_from_session, client_ip
        )
        return HttpResponse(status=404)
    except User.DoesNotExist:
        logger.error(
            "Attempt to comment by user ID from session that does not exist in DB. "
            "User ID: %s, Post ID: %s, IP: %s. Flushing session.",
            user_id_from_session, post_id, client_ip
        )
        request.session.flush() # 세션 초기화
        return HttpResponse(status=403) # Forbidden

    raw_content = request.POST.get('content', '')
    if not raw_content.strip():
        logger.info(
            "Attempt to add empty comment by User '%s' (ID: %s) on post ID %s. IP: %s",
            user.username, user.user_id, post.post_id, client_ip
        )
        return HttpResponse("Comment content cannot be empty.", status=400)

    # 강화된 bleach 설정:
    # 허용할 태그는 기존과 유사하게 유지하되, 필요에 따라 최소화 가능.
    allowed_tags = [
        'p', 'br', 'b', 'i', 'u', 'strong', 'em', 'a',
        'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'hr'
    ]
    # 속성 허용을 더 엄격하게 변경:
    # - 'a' 태그의 'target' 속성 제거 (탭내빙 방지)
    # - 모든 태그에 'class' 속성을 허용하던 '*' 규칙 제거 (필요시 특정 태그에만 제한적으로 허용)
    # - 'a' 태그에 'rel' 속성 추가하여 'noopener', 'noreferrer' 사용 권장
    allowed_attributes = {
        'a': ['href', 'title', 'rel'], # 'target' 속성 제거
        # 예시: 'p': ['class'], # p 태그에는 class 속성 허용 (특정 값만 허용하도록 더 제한 가능)
        #       'code': ['class'] # code 태그에 'language-python' 같은 클래스 허용 시
    }
    # 프로토콜은 'http', 'https'로 제한 (기존 'mailto' 제거)
    allowed_protocols = ['http', 'https']

    safe_content = bleach.clean(
        raw_content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        protocols=allowed_protocols,
        strip=True,         # 허용되지 않은 태그와 그 내용을 제거
        strip_comments=True # HTML 주석 제거
    )

    # 로깅 강화: 원본 입력과 정제된 입력 비교
    if raw_content != safe_content:
        logger.warning(
            "POTENTIAL MALICIOUS OR UNEXPECTED INPUT (comment sanitization occurred): "
            "User '%s' (ID: %s) on Post ID %s. IP: %s. "
            "Raw content: %r. Sanitized content: %r.",
            user.username, user.user_id, post.post_id, client_ip, raw_content, safe_content
        )
    else:
        logger.info(
            "New comment added: User '%s' (ID: %s) on Post ID %s. IP: %s. Content: %r",
            user.username, user.user_id, post.post_id, client_ip, safe_content
        )

    # DB에는 항상 정제된 내용을 저장
    Comment.objects.create(post=post, user=user, content=safe_content)

    return HttpResponse(status=200)

# URL 패턴 정의
urlpatterns = [
    path('login/<int:user_id>/', login, name='login'),
    path('posts/', view_posts, name='view_posts'),
    path('search/', search_posts, name='search_posts'),
    path('posts/<int:post_id>/comment/', add_comment, name='add_comment'),
]

# 애플리케이션 실행 부분
if __name__ == '__main__':
    # DB 테이블 생성 (개발/테스트용 간이 방식. 실제로는 Django 마이그레이션 사용)
    existing_tables = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        for model_cls in [User, Post, Comment]:
            if model_cls._meta.db_table not in existing_tables:
                try:
                    schema_editor.create_model(model_cls)
                    logger.info(f"Created table: {model_cls._meta.db_table}")
                except Exception as e:
                    logger.error(f"Failed to create table {model_cls._meta.db_table}: {e}")

    # 샘플 데이터 (get_or_create 사용으로 멱등성 확보)
    try:
        user1, created1 = User.objects.get_or_create(username='alice', defaults={'is_admin': False})
        if created1: logger.info("Created sample user: alice")
        user2, created2 = User.objects.get_or_create(username='bob', defaults={'is_admin': True})
        if created2: logger.info("Created sample user: bob")

        post1, created_p1 = Post.objects.get_or_create(
            user=user1, title='Django Tips',
            defaults={'content': 'Learn how to use Django effectively.'}
        )
        if created_p1: logger.info("Created sample post: Django Tips")

        post2, created_p2 = Post.objects.get_or_create(
            user=user2, title='Board Rules',
            defaults={'content': 'Please be respectful.'}
        )
        if created_p2: logger.info("Created sample post: Board Rules")

        # 댓글은 고유성을 판단할 명확한 필드가 없으므로, 조건부로 생성하거나 단순 create 사용
        if not Comment.objects.filter(post=post1, user=user2, content='Great post!').exists():
            Comment.objects.create(post=post1, user=user2, content='Great post!')
            logger.info("Created sample comment for 'Django Tips'")
    except Exception as e:
        logger.error(f"Error creating sample data: {e}")

    from django.core.management import execute_from_command_line
    logger.info("Starting Django development server at http://0.0.0.0:8000/")
    # 외부 접속 허용을 위해 0.0.0.0 사용, 포트는 8000 (기본값)
    execute_from_command_line(['', 'runserver', '127.0.0.1:8000'])