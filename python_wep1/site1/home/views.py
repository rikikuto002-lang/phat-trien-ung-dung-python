from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.http import JsonResponse

# Create your views here.
def home_view(request):
    return render(request, 'home.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        # Add your authentication logic here
    return render(request, 'login.html')

def signup_view(request):
    return render(request, 'signup.html')

def product_detail_view(request, product_id=None):
    """Display product detail page"""
    # In production, fetch product from database using product_id
    # For now, just render the template with sample data
    return render(request, 'thongTinSP.html')

def cart_view(request):
    """Display shopping cart page"""
    # In production, fetch cart items from database or session
    # For now, just render the template with sample data
    return render(request, 'gioHang.html')

def checkout_view(request):
    """Display checkout/payment page"""
    # In production, validate cart items and fetch order details
    # For now, just render the template with sample data
    return render(request, 'thanhToan.html')

def google_auth(request):
    """Handle Google login - redirect to home after authentication"""
    # In production, you would implement OAuth2 flow with Google
    # For now, this redirects to home
    return redirect('home')

def facebook_auth(request):
    """Handle Facebook login - redirect to home after authentication"""
    # In production, you would implement OAuth2 flow with Facebook
    # For now, this redirects to home
    return redirect('home')

def google_auth_signup(request):
    """Handle Google signup - redirect to login after authentication"""
    # In production, you would implement OAuth2 flow with Google
    # For now, this redirects to login
    return redirect('login')

def facebook_auth_signup(request):
    """Handle Facebook signup - redirect to login after authentication"""
    # In production, you would implement OAuth2 flow with Facebook
    # For now, this redirects to login
    return redirect('login')