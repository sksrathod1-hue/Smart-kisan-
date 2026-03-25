from django.contrib import admin
from .models import Scheme, ApplicationRequest, Notification


# -----------------------------
# SCHEME ADMIN
# -----------------------------
class SchemeAdmin(admin.ModelAdmin):
    list_display = ('scheme_name', 'scheme_type', 'state', 'department')
    search_fields = ('scheme_name', 'state')
    list_filter = ('scheme_type', 'state')


# -----------------------------
# APPLICATION REQUEST ADMIN
# -----------------------------
class ApplicationRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'mobile', 'state', 'status', 'created_at')
    search_fields = ('name', 'mobile')
    list_filter = ('status', 'state')


# -----------------------------
# NOTIFICATION ADMIN
# -----------------------------
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'created_at')


# REGISTER MODELS
admin.site.register(Scheme, SchemeAdmin)
admin.site.register(ApplicationRequest, ApplicationRequestAdmin)
admin.site.register(Notification, NotificationAdmin)