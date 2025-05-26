from django.conf import settings
from django.db import models, connection
from django.http import HttpResponse, JsonResponse
from django.template import Template, Context # 사용되지 않아 주석 처리 또는 삭제 가능
from django.urls import path
from django.utils import timezone
from django.views.decorators.http import require_POST # 로그인 시 POST 강제
from django.views.decorators.csrf import csrf_protect # CSRF 보호 데코레이터
from django.utils.html import escape # XSS 방지를 위한 escape 함수

settings.configure(
    SECRET_KEY='your-secret-key', # 실제 운영 시 강력한 무작위 키로 변경
    DEBUG=True, # 실제 운영 시 False로 변경
    ALLOWED_HOSTS=['*'], # 실제 운영 시 특정 호스트 지정
    SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
    INSTALLED_APPS=[
        'django.contrib.contenttypes',
        'django.contrib.auth', # Django 기본 인증 시스템 (A2 해결에 권장)
        'django.contrib.sessions',
    ],
    MIDDLEWARE=[
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware', # A1: CSRF 미들웨어 추가
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
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True) # username은 고유해야 함
    # A2: 실제 시스템에서는 Django의 AbstractUser를 상속받고 비밀번호는 해시되어 저장되어야 합니다.
    # 여기서는 데모를 위해 간단한 password 필드를 추가합니다.
    password = models.CharField(max_length=128) # 실제로는 해시된 비밀번호 저장
    is_admin = models.BooleanField(default=False)
    class Meta:
        app_label = 'shop' # 임의의 app_label, 실제 Django 프로젝트 구조에서는 앱 이름 사용
        db_table = 'users'

class Product(models.Model):
    product_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    class Meta:
        app_label = 'shop'
        db_table = 'products'

class Order(models.Model):
    order_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    ordered_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'shop'
        db_table = 'orders'

# A2: 로그인 방식 변경
# 이전: path('login/<int:user_id>/', login, name='login')
# 변경: path('login/', login, name='login')
@require_POST # POST 요청만 허용
# @csrf_protect # 폼을 통해 로그인한다면 CSRF 보호 필요. API 형태라면 다른 토큰 기반 인증 고려.
def login(request):
    # 실제 애플리케이션에서는 Django Form 또는 DRF Serializer를 사용하여 입력값 검증 권장
    username = request.POST.get('username')
    password = request.POST.get('password')

    if not username or not password:
        return HttpResponse('Username and password required', status=400)

    # 중요: 아래는 매우 단순화된 인증 방식입니다.
    # 실제 운영 환경에서는 django.contrib.auth.authenticate 및 login 함수를 사용하고,
    # 비밀번호는 반드시 해시하여 저장하고 비교해야 합니다. (e.g., user.check_password(password))
    user = User.objects.filter(username=username).first()
    if user and user.password == password: # 여기서는 단순 문자열 비교 (매우 비보안적)
        request.session['user_id'] = user.user_id
        request.session['is_admin'] = user.is_admin
        request.session['username'] = user.username # 세션에 username 추가 (선택 사항)
        return HttpResponse('Login successful', status=200)
    else:
        return HttpResponse('Invalid credentials', status=401)

def logout(request): # 기본적인 로그아웃 기능 추가
    try:
        del request.session['user_id']
        del request.session['is_admin']
        del request.session['username']
    except KeyError:
        pass
    return HttpResponse('Logged out', status=200)

def list_products(request):
    products = Product.objects.filter(is_active=True).values('product_id', 'name', 'description', 'price', 'stock')
    return JsonResponse(list(products), safe=False)

@csrf_protect # A1: POST 요청이므로 CSRF 보호 적용 (add_product는 관리자만)
def add_product(request):
    if not request.session.get('is_admin', False):
        return HttpResponse('403 Forbidden: Admin access required', status=403)
    
    if request.method == 'POST':
        data = request.POST
        # A7: XSS 방지를 위해 입력값 이스케이프 처리
        # 더 강력한 XSS 방지를 위해서는 bleach와 같은 라이브러리로 화이트리스트 기반 필터링 권장
        Product.objects.create(
            name=escape(data.get('name', '')), # .get으로 안전하게 값 가져오고 escape 처리
            description=escape(data.get('description', '')), # 설명도 escape 처리
            price=data.get('price'), # DecimalField는 Django가 어느정도 검증
            stock=data.get('stock')  # PositiveIntegerField는 Django가 어느정도 검증
        )
        return HttpResponse('Product added successfully', status=200)
    return HttpResponse('Invalid request method for add_product', status=405)


@csrf_protect # A1: CSRF 보호 적용
def order_product(request, product_id):
    if not request.session.get('user_id'):
        return HttpResponse('401 Unauthorized: Login required', status=401)

    if request.method == 'POST':
        try:
            user = User.objects.get(user_id=request.session['user_id'])
            product = Product.objects.get(product_id=product_id, is_active=True) # 활성화된 제품만 주문 가능
            quantity_str = request.POST.get('quantity')
            if not quantity_str or not quantity_str.isdigit():
                return HttpResponse('400 Bad Request: Invalid quantity', status=400)
            
            quantity = int(quantity_str)
            if quantity <= 0:
                 return HttpResponse('400 Bad Request: Quantity must be positive', status=400)

            if product.stock >= quantity:
                product.stock -= quantity
                product.save()
                Order.objects.create(
                    user=user,
                    product=product,
                    quantity=quantity,
                    ordered_at=timezone.now()
                )
                return HttpResponse('Order successful', status=200)
            else:
                return HttpResponse('400 Bad Request: Insufficient stock', status=400)
        except User.DoesNotExist:
            return HttpResponse('401 Unauthorized: Invalid user session', status=401)
        except Product.DoesNotExist:
            return HttpResponse('404 Not Found: Product not found or not active', status=404)
        except Exception as e: # 기타 예외 처리
            # 실제 운영에서는 로깅을 통해 에러를 추적해야 합니다.
            # print(f"Error during ordering: {e}") 
            return HttpResponse('500 Internal Server Error', status=500)
    return HttpResponse('Invalid request method for order_product', status=405)


def view_orders(request):
    if not request.session.get('user_id'):
        return HttpResponse('401 Unauthorized: Login required', status=401)
    
    try:
        user = User.objects.get(user_id=request.session['user_id'])
        orders = Order.objects.filter(user=user).values('order_id', 'product__name', 'quantity', 'ordered_at')
        return JsonResponse(list(orders), safe=False)
    except User.DoesNotExist:
        return HttpResponse('401 Unauthorized: Invalid user session', status=401)

urlpatterns = [
    path('login/', login, name='login'), # A2: 로그인 URL 변경
    path('logout/', logout, name='logout'), # 로그아웃 URL 추가
    path('products/', list_products, name='list_products'),
    path('products/add/', add_product, name='add_product'),
    path('products/<int:product_id>/order/', order_product, name='order_product'),
    path('orders/', view_orders, name='view_orders'),
]

if __name__ == '__main__':
    # DB 테이블 생성 (이미 존재하면 생성 안 함)
    existing_tables = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if User._meta.db_table not in existing_tables: schema_editor.create_model(User)
        if Product._meta.db_table not in existing_tables: schema_editor.create_model(Product)
        if Order._meta.db_table not in existing_tables: schema_editor.create_model(Order)

    # 테스트 데이터 생성 (이미 존재하면 중복 생성될 수 있으므로, get_or_create 등 사용 권장)
    # User.objects.all().delete() # 필요시 기존 데이터 삭제
    # Product.objects.all().delete()
    # Order.objects.all().delete()

    # A2: User 생성 시 password 필드 추가 (실제로는 해시된 비밀번호 사용)
    user_shopper, _ = User.objects.get_or_create(
        username='shopper', 
        defaults={'password': 'shopper_password', 'is_admin': False} # 매우 약한 비밀번호 (예시용)
    )
    user_admin, _ = User.objects.get_or_create(
        username='admin', 
        defaults={'password': 'admin_password', 'is_admin': True} # 매우 약한 비밀번호 (예시용)
    )

    # Product 데이터 (get_or_create 사용)
    laptop, _ = Product.objects.get_or_create(
        name='Laptop', 
        defaults={'description': 'A powerful laptop', 'price': 1500.00, 'stock': 5, 'is_active': True}
    )
    phone, _ = Product.objects.get_or_create(
        name='Phone', 
        defaults={'description': 'A smart phone', 'price': 800.00, 'stock': 10, 'is_active': True}
    )

    # Order 데이터 (예시, 필요시 생성)
    if not Order.objects.filter(user=user_shopper, product=laptop).exists():
        Order.objects.create(user=user_shopper, product=laptop, quantity=1)
    
    if not Order.objects.filter(user=user_admin, product=phone).exists():
        Order.objects.create(user=user_admin, product=phone, quantity=2)

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver', '0.0.0.0:8000']) # 모든 인터페이스에서 접속 가능하게 변경