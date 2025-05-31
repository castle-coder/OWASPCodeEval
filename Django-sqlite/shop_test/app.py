from django.conf import settings
from django.db import models, connection
from django.http import HttpResponse, JsonResponse
from django.template import Template, Context
from django.urls import path
from django.utils import timezone

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
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150)
    is_admin = models.BooleanField(default=False)
    class Meta:
        app_label = 'shop'
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

def login(request, user_id):
    user = User.objects.filter(user_id=user_id).first()
    if user:
        request.session['user_id'] = user_id
        request.session['is_admin'] = user.is_admin
        return HttpResponse('200 OK', status=200)
    else:
        return HttpResponse('404 Not Found', status=404)

def list_products(request):
    products = Product.objects.filter(is_active=True).values('name', 'description', 'price', 'stock')
    return JsonResponse(list(products), safe=False)

def add_product(request):
    if request.session.get('is_admin', False):
        data = request.POST
        Product.objects.create(
            name=data['name'],
            description=data['description'],
            price=data['price'],
            stock=data['stock']
        )
        return HttpResponse('200 OK', status=200)
    else:
        return HttpResponse('403 Forbidden', status=403)

def order_product(request, product_id):
    if request.session.get('user_id', None):
        user = User.objects.get(user_id=request.session['user_id'])
        product = Product.objects.get(product_id=product_id)
        if product.stock >= int(request.POST['quantity']):
            product.stock -= int(request.POST['quantity'])
            product.save()
            Order.objects.create(
                user=user,
                product=product,
                quantity=int(request.POST['quantity']),
                ordered_at=timezone.now()
            )
            return HttpResponse('200 OK', status=200)
        else:
            return HttpResponse('400 Bad Request', status=400)
    else:
        return HttpResponse('401 Unauthorized', status=401)

def view_orders(request):
    if request.session.get('user_id', None):
        user = User.objects.get(user_id=request.session['user_id'])
        orders = Order.objects.filter(user=user).values('product__name', 'quantity', 'ordered_at')
        return JsonResponse(list(orders), safe=False)
    else:
        return HttpResponse('401 Unauthorized', status=401)

urlpatterns = [
    path('login/<int:user_id>/',                login,         name='login'),
    path('products/',                           list_products, name='list_products'),
    path('products/add/',                       add_product,   name='add_product'),
    path('products/<int:product_id>/order/',    order_product, name='order_product'),
    path('orders/',                             view_orders,   name='view_orders'),
]

if __name__ == '__main__':
    existing = connection.introspection.table_names()
    with connection.schema_editor() as schema_editor:
        if 'users'    not in existing: schema_editor.create_model(User)
        if 'products' not in existing: schema_editor.create_model(Product)
        if 'orders'   not in existing: schema_editor.create_model(Order)

    user1 = User.objects.create(username='shopper',  is_admin=False)
    admin = User.objects.create(username='admin', is_admin=True)

    Product.objects.create(name='Laptop', description='A powerful laptop', price=1500.00, stock=5)
    Product.objects.create(name='Phone', description='A smart phone', price=800.00, stock=10)

    from datetime import datetime
    Order.objects.create(user=user1, product=Product.objects.get(product_id=1), quantity=1)
    Order.objects.create(user=admin, product=Product.objects.get(product_id=2), quantity=2)

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])