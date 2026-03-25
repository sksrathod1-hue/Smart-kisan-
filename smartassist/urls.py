from django.contrib import admin
from django.urls import path
from farmers.views import dashboard, recommend_schemes

urlpatterns = [
    path('admin/', admin.site.urls),

    # 🔥 Dashboard URLs
    path('', dashboard, name='home'),              # default
    path('dashboard/', dashboard, name='dashboard'),  # NEW (important)

    # 🔥 AI Recommendation
    path('recommend/', recommend_schemes, name='recommend'),
]