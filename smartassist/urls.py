from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf.urls.i18n import i18n_patterns

from farmers.views import (
    dashboard,
    recommend_schemes,
    apply_scheme,
    my_applications,
    chatbot,
    schemes_by_state_api,
    register,
    profile,
    home,
    scheme_awareness,
    apply_for_assistance,
    application_status,
    admin_dashboard,
    manage_schemes,
    update_application_status,
    apply_scheme_admin,
    reports,
    set_language
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/setlang/', set_language, name='set_language'),
]

urlpatterns += i18n_patterns(
    # Home
    path('', home, name='home'),

    # Dashboard
    path('dashboard/', dashboard, name='dashboard'),

    # Citizen Pages
    path('schemes/', scheme_awareness, name='scheme_awareness'),
    path('apply/', apply_for_assistance, name='apply_assistance'),
    path('status/', application_status, name='application_status'),

    # Recommendation
    path('recommend/', recommend_schemes, name='recommend'),

    # Apply scheme
    path('apply/<int:scheme_id>/', apply_scheme, name='apply'),

    # My applications
    path('my-applications/', my_applications, name='my_apps'),

    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', register, name='register'),
    path('profile/', profile, name='profile'),

    # Password Reset
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='password_reset.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),

    # Admin/Volunteer
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    path('manage-schemes/', manage_schemes, name='manage_schemes'),
    path('update-status/<int:app_id>/', update_application_status, name='update_status'),
    path('apply-scheme/<int:app_id>/<int:scheme_id>/', apply_scheme_admin, name='apply_scheme_admin'),
    path('reports/', reports, name='reports'),

    # ✅ CHATBOT (IMPORTANT)
    path('chatbot/', chatbot, name='chatbot'),

    # API endpoints
    path('api/state-schemes/<str:state_name>/', schemes_by_state_api, name='state_schemes_api'),

    prefix_default_language=False
)