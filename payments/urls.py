from django.urls import path
from . import views

urlpatterns = [
    path('', views.payment_view, name='payment_page'),
    path('create-checkout-session/',
         views.create_checkout_session,
         name='create_checkout_session'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('success/', views.success_view, name='success'),
    path('cancel/', views.cancel_view, name='cancel'),
]
