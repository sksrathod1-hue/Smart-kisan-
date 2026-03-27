from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile, Scheme, ApplicationRequest


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email']


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'state', 'district', 'age', 'gender', 'education', 'income_range', 'category']


class CitizenApplicationForm(forms.ModelForm):
    class Meta:
        model = ApplicationRequest
        fields = ['name', 'age', 'gender', 'mobile', 'email', 'education', 'income', 'category', 'state', 'district']
        widgets = {
            'income': forms.NumberInput(attrs={'placeholder': 'Annual Income in Rupees'}),
        }


class SchemeForm(forms.ModelForm):
    class Meta:
        model = Scheme
        fields = '__all__'