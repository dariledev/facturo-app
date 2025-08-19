# invoice_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Pour les fichiers médias
from django.conf.urls.static import static # Pour les fichiers médias

urlpatterns = [
    path('admin/', admin.site.urls),
     path('', include('pwa.urls')),
    path('', include('core.urls')), # Incluez les URLs de votre application core
]

# Pour servir les fichiers médias en mode développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)