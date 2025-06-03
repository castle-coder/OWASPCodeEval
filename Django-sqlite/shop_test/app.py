from django.conf import settings
from django.db import models, connection
from django.http import HttpResponse, JsonResponse
from django.template import Template, Context
from django.urls import path

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
        return HttpResponse('200 OK')
    else:
        return HttpResponse('404 Not Found')

def list_products(request):
    products = Product.objects.filter(is_active=True)
    response = '<ul>'
    for product in products:
        response += f'<li>{product.name} - {product.description} - ${product.price} - Stock: {product.stock}</li>'
    response += '</ul>'
    return HttpResponse(response)

def add_product(request):
    if request.session.get('is_admin'):
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        Product.objects.create(name=name, description=description, price=price, stock=stock)
        return HttpResponse('200 OK')
    else:
        return HttpResponse('403 Forbidden')

def order_product(request, product_id):
    if request.session.get('user_id'):
        user_id = request.session.get('user_id')
        product = Product.objects.filter(product_id=product_id).first()
        if product and product.stock >= int(request.POST.get('quantity')):
            product.stock -= int(request.POST.get('quantity'))
            product.save()
            Order.objects.create(user_id=user_id, product_id=product_id, quantity=int(request.POST.get('quantity')))
            return HttpResponse('200 OK')
        else:
            return HttpResponse('400 Bad Request')
    else:
        return HttpResponse('401 Unauthorized')

def view_orders(request):
    if request.session.get('user_id'):
        user_id = request.session.get('user_id')
        orders = Order.objects.filter(user_id=user_id)
        response = '<ul>'
        for order in orders:
            response += f'<li>{order.product.name} - Quantity: {order.quantity} - Ordered At: {order.ordered_at}</li>'
        response += '</ul>'
        return HttpResponse(response)
    else:
        return HttpResponse('401 Unauthorized')

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

    product1 = Product.objects.create(name='Laptop', description='A powerful laptop', price=1500.00, stock=5)
    product2 = Product.objects.create(name='Phone', description='A smart phone', price=800.00, stock=10)

    Order.objects.create(user=user1, product=product1, quantity=1)
    Order.objects.create(user=admin, product=product2, quantity=2)

    from django.core.management import execute_from_command_line
    execute_from_command_line(['', 'runserver'])