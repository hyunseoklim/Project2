from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static
from apps.accounts import views as account_views
urlpatterns = [
    path('', account_views.home, name='home'),
    
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('businesses/', include('apps.businesses.urls')),  
    path('transactions/', include('apps.transactions.urls')),
    path('tax/', include('apps.tax.urls')),  

]

# 최재용_미디어파일 읽을때 사용하는 코드
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

