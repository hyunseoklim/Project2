from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('businesses/', include('apps.businesses.urls')),  
    path('transactions/', include('apps.transactions.urls')),

]