from django.urls import path
from . import views

urlpatterns = [
    path('', views.contact_form, name='contact_form'),
    path('submit/', views.submit_form, name='submit_form'),
    path('thank-you/', views.thank_you, name='thank_you'),
]
