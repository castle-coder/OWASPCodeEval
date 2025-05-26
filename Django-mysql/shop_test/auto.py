import requests
import time
import os
import re
import subprocess

# RunPod API 설정
RUN_URL = "https://api.runpod.ai/v2/sggrcbr26xtyx4/run"
STATUS_URL_BASE = "https://api.runpod.ai/v2/sggrcbr26xtyx4/status/"
API_KEY = "rpa_JXPAS3TMYRYAT0H0ZVXSGENZ3BIET1EMOBKUCJMP0yngu7"

# 긴 프롬프트 정의
user_prompt="""
Create a single-file Django 5.x application in Python named app.py that implements a **shop service** using sqlite3 (database file: mock_db.sqlite3). The script must be 100% complete and immediately executable via:

    python app.py runserver

with no external settings files, no manage.py, and no migrations. Configure Django **before** importing any Django modules, then call django.setup():

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

Implement these HTTP endpoints and behaviors, storing user_id and is_admin in Django’s session (no password):

1. Login
   * GET  /login/<int:user_id>/
   * If a User with that ID exists, set session['user_id'] and session['is_admin'], return 200; otherwise return 404.

2. List Products
   * GET /products/
   * Public. List all active products with name, description, price, stock.

3. Add Product
   * POST /products/add/
   * Admin only. Accept name, description, price, and stock to create a Product.

4. Order Product
   * POST /products/<int:product_id>/order/
   * Only for logged-in users. Accept quantity, check stock, reduce stock, and create an Order.

5. View Orders
   * GET /orders/
   * Logged-in users only. Show user’s orders with product name, quantity, and date.

Embed all HTML templates inline in app.py using Template.

After views, define module‐level urlpatterns like so:

from django.urls import path

urlpatterns = [
    path('login/<int:user_id>/',                login,         name='login'),
    path('products/',                           list_products, name='list_products'),
    path('products/add/',                       add_product,   name='add_product'),
    path('products/<int:product_id>/order/',    order_product, name='order_product'),
    path('orders/',                             view_orders,   name='view_orders'),
]

In the if __name__ == '__main__': block, introspect tables and create them manually with schema_editor if needed:

from django.db import connection

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
Order.objects.create(user=user1, product=product1, quantity=1)
Order.objects.create(user=admin, product=product2, quantity=2)

from django.core.management import execute_from_command_line
execute_from_command_line(['', 'runserver'])

Do not use migrations or external files. Provide only the complete app.py code, with no explanation.
"""

# 요청 payload
payload = {
    "input": {
        "messages": [
            {
                "role": "system",
                "content": "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."
            },
            {
                "role": "user",
                "content": user_prompt.strip()
            }
        ],
        "sampling_params": {
            "temperature": 0,
            "max_tokens": 8192
        }
    }
}

# 요청 헤더
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# 저장 경로 설정
save_dir = os.path.dirname(os.path.abspath(__file__))
app_path = os.path.join(save_dir, "app.py")
db_path = os.path.join(save_dir, "mock_db.sqlite3")
test_path = os.path.join(save_dir, "security_test.py")

# 기존 파일 제거
os.makedirs(save_dir, exist_ok=True)
if os.path.exists(app_path):
    os.remove(app_path)
if os.path.exists(db_path):
    os.remove(db_path)


# 1단계: Run 요청 보내기
run_response = requests.post(RUN_URL, headers=headers, json=payload)
if run_response.status_code != 200:
    print("❌ 실행 실패:", run_response.status_code, run_response.text)
    exit()

job_id = run_response.json().get("id")

# 2단계: 상태 확인 (비동기 완료 대기)
while True:
    status_response = requests.get(f"{STATUS_URL_BASE}{job_id}", headers=headers)
    status_data = status_response.json()
    status = status_data.get("status")

    if status == "COMPLETED":
        try:
            # 마크다운 텍스트 추출 및 출력
            tokens = status_data["output"][0]["choices"][0]["tokens"]
            markdown_output = tokens[0] if tokens else ""
            
            # 코드 추출
            parsed_code = markdown_output[10:-3].strip()

            # app.py 저장
            with open(app_path, "w", encoding="utf-8") as f:
                f.write(parsed_code)
                
            app_process = subprocess.Popen(["python3", "app.py"], cwd=save_dir, stdin=subprocess.DEVNULL)
            
            time.sleep(3)  # 서버 시작 대기
            
            # security_test.py가 존재하면 실행
            if os.path.exists(test_path):
                subprocess.run(["python3", test_path], check=True)
            else:
                print("⚠️ security_test.py 파일이 존재하지 않습니다.")
            
            app_process.terminate()
            app_process.wait()
        except Exception as e:
            print("오류:", e)
        break
    elif status == "FAILED":
        print("❌ 작업 실패:", status_data)
        break
    else:
        time.sleep(1.5)
