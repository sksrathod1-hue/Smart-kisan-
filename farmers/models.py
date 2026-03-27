from django.db import models
from django.contrib.auth.models import User


# -----------------------------
# USER PROFILE MODEL (ENHANCED)
# -----------------------------
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=[
        ('citizen', 'Citizen'),
        ('volunteer', 'Volunteer'),
        ('admin', 'Admin')
    ], default='citizen')
    phone = models.CharField(max_length=15, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    age = models.IntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    education = models.CharField(max_length=100, blank=True, null=True)
    income_range = models.CharField(max_length=50, blank=True, null=True)
    category = models.CharField(max_length=50, blank=True, null=True)  # SC/ST/OBC/General

    def __str__(self):
        return f"{self.user.username}'s profile"


# -----------------------------
# SCHEME MODEL
# -----------------------------
class Scheme(models.Model):
    scheme_name = models.CharField(max_length=255)
    scheme_type = models.CharField(max_length=50, choices=[
        ('Central', 'Central'),
        ('State', 'State')
    ])
    state = models.CharField(max_length=100)
    department = models.CharField(max_length=100)

    # 🔥 DETAILS
    description = models.TextField(blank=True, null=True)
    benefits = models.TextField(blank=True, null=True)
    eligibility = models.TextField(blank=True, null=True)
    documents_required = models.TextField(blank=True, null=True)
    official_website = models.URLField(null=True, blank=True)
    apply_link = models.URLField(null=True, blank=True)

    # 🔥 FILTERING FIELDS
    min_age = models.IntegerField(default=18)
    max_age = models.IntegerField(default=65)
    income_limit = models.IntegerField(default=1000000)
    category = models.CharField(max_length=50, default="All")  # SC/ST/OBC/General/All
    education_required = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.scheme_name


# -----------------------------
# APPLICATION REQUEST MODEL
# -----------------------------
class ApplicationRequest(models.Model):
    STATUS_CHOICES = [
        ('Submitted', 'Submitted'),
        ('Under Review', 'Under Review'),
        ('Applied', 'Applied'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    scheme = models.ForeignKey(Scheme, on_delete=models.CASCADE, null=True, blank=True)

    # Citizen details (copied for reference)
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    gender = models.CharField(max_length=10)
    mobile = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    education = models.CharField(max_length=100)
    income = models.IntegerField()
    category = models.CharField(max_length=50)
    state = models.CharField(max_length=100)
    district = models.CharField(max_length=100)

    # Application details
    applied_by = models.ForeignKey(User, related_name='applied_applications', on_delete=models.SET_NULL, null=True, blank=True)  # Volunteer/Admin
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Submitted')
    application_number = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.scheme.scheme_name if self.scheme else 'No Scheme'}"

    def get_status_class(self):
        return {
            'Submitted': 'status-submitted',
            'Under Review': 'status-underreview',
            'Applied': 'status-applied',
            'Approved': 'status-approved',
            'Rejected': 'status-rejected'
        }.get(self.status, 'status-submitted')


# -----------------------------
# NOTIFICATION MODEL
# -----------------------------
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES, default='email')
    subject = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.notification_type} to {self.user.username}"