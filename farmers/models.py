from django.db import models
from django.contrib.auth.models import User


# -----------------------------
# SCHEME MODEL (FINAL CORRECT)
# -----------------------------
class Scheme(models.Model):
    scheme_name = models.CharField(max_length=255)
    scheme_type = models.CharField(max_length=50)
    state = models.CharField(max_length=100)
    department = models.CharField(max_length=100)

    # 🔥 AI RULE FIELDS
    min_age = models.IntegerField(default=18)
    max_age = models.IntegerField(default=65)
    income_limit = models.IntegerField(default=1000000)
    category = models.CharField(max_length=50, default="All")

    def __str__(self):
        return self.scheme_name


# -----------------------------
# APPLICATION REQUEST
# -----------------------------
class ApplicationRequest(models.Model):

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Applied', 'Applied'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    name = models.CharField(max_length=100)
    age = models.IntegerField()
    gender = models.CharField(max_length=10)

    mobile = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)

    education = models.CharField(max_length=100)
    income = models.CharField(max_length=100)
    category = models.CharField(max_length=50)

    state = models.CharField(max_length=100)
    district = models.CharField(max_length=100)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# -----------------------------
# NOTIFICATION MODEL
# -----------------------------
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}"