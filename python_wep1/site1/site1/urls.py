"""
URL configuration for site1 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from home import views as home_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_views.home_view, name='home'),
    path('login/', home_views.login_view, name='login'),
    path('signup/', home_views.signup_view, name='signup'),
    path('product/<int:product_id>/', home_views.product_detail_view, name='product_detail'),
    path('product/', home_views.product_detail_view, name='product'),
    path('gioHang/', home_views.cart_view, name='cart'),
    path('thanhToan/', home_views.checkout_view, name='checkout'),
    path('auth/google/', home_views.google_auth, name='google_auth'),
    path('auth/facebook/', home_views.facebook_auth, name='facebook_auth'),
    path('auth/google/signup/', home_views.google_auth_signup, name='google_auth_signup'),
    path('auth/facebook/signup/', home_views.facebook_auth_signup, name='facebook_auth_signup'),
]
