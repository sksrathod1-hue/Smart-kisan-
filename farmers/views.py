from django.shortcuts import render, redirect
from django.db.models import Count, Q
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext as _, activate
from .models import ApplicationRequest, Scheme, Notification, UserProfile
from .forms import UserRegisterForm, UserUpdateForm, UserProfileForm, CitizenApplicationForm, SchemeForm
import json


# -----------------------------
# AUTHENTICATION VIEWS
# -----------------------------
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'register.html', {'form': form})


@login_required
def profile(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, instance=user_profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, _('Your profile has been updated!'))
            return redirect('profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = UserProfileForm(instance=user_profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }
    return render(request, 'profile.html', context)


# -----------------------------
# CITIZEN VIEWS
# -----------------------------
def home(request):
    """Home page with project overview"""
    return render(request, 'home.html')


@login_required
def scheme_awareness(request):
    """Display all available schemes for awareness"""
    schemes = Scheme.objects.all()
    return render(request, 'scheme_awareness.html', {'schemes': schemes})


@login_required
def apply_for_assistance(request):
    """Citizen application form"""
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = CitizenApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.status = 'Submitted'
            application.save()

            # Create notification
            Notification.objects.create(
                user=request.user,
                notification_type='email',
                subject=_('Application Submitted'),
                message=_('Your application for government scheme assistance has been submitted successfully.')
            )

            messages.success(request, _('Application submitted for assistance. Our volunteers will help you apply for suitable schemes.'))
            return redirect('application_status')
    else:
        # Pre-fill form with profile data
        initial_data = {
            'name': request.user.get_full_name() or request.user.username,
            'email': request.user.email,
            'mobile': user_profile.phone,
            'age': user_profile.age,
            'gender': user_profile.gender,
            'education': user_profile.education,
            'category': user_profile.category,
            'state': user_profile.state,
            'district': user_profile.district,
        }
        form = CitizenApplicationForm(initial=initial_data)

    return render(request, 'apply.html', {'form': form})


@login_required
def application_status(request):
    """Track application status"""
    applications = ApplicationRequest.objects.filter(user=request.user)
    return render(request, 'application_status.html', {'applications': applications})


# -----------------------------
# ADMIN/VOLUNTEER VIEWS
# -----------------------------
@login_required
def admin_dashboard(request):
    """Admin/Volunteer dashboard"""
    user_profile = UserProfile.objects.get(user=request.user)
    if user_profile.role not in ['volunteer', 'admin']:
        return redirect('dashboard')

    # Get all applications
    applications = ApplicationRequest.objects.all().order_by('-created_at')

    # Statistics
    total_applications = applications.count()
    pending = applications.filter(status='Submitted').count()
    under_review = applications.filter(status='Under Review').count()
    applied = applications.filter(status='Applied').count()
    approved = applications.filter(status='Approved').count()
    rejected = applications.filter(status='Rejected').count()

    context = {
        'applications': applications[:10],  # Recent 10
        'total_applications': total_applications,
        'pending': pending,
        'under_review': under_review,
        'applied': applied,
        'approved': approved,
        'rejected': rejected,
    }
    return render(request, 'admin_dashboard.html', context)


@login_required
def manage_schemes(request):
    """Manage government schemes"""
    user_profile = UserProfile.objects.get(user=request.user)
    if user_profile.role not in ['volunteer', 'admin']:
        return redirect('dashboard')

    if request.method == 'POST':
        form = SchemeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Scheme added successfully!'))
            return redirect('manage_schemes')
    else:
        form = SchemeForm()

    schemes = Scheme.objects.all()
    return render(request, 'manage_schemes.html', {'form': form, 'schemes': schemes})


@login_required
def update_application_status(request, app_id):
    """Update application status"""
    user_profile = UserProfile.objects.get(user=request.user)
    if user_profile.role not in ['volunteer', 'admin']:
        return redirect('dashboard')

    application = ApplicationRequest.objects.get(id=app_id)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        notes = request.POST.get('notes')
        application.status = new_status
        application.notes = notes
        application.applied_by = request.user
        application.save()

        # Send notification
        Notification.objects.create(
            user=application.user,
            notification_type='email',
            subject=_('Application Status Updated'),
            message=_(f'Your application status has been updated to: {new_status}')
        )

        messages.success(request, _('Application status updated!'))
        return redirect('admin_dashboard')

    return render(request, 'update_status.html', {'application': application})


@login_required
def apply_scheme_admin(request, app_id, scheme_id):
    """Apply for scheme on behalf of citizen"""
    user_profile = UserProfile.objects.get(user=request.user)
    if user_profile.role not in ['volunteer', 'admin']:
        return redirect('dashboard')

    application = ApplicationRequest.objects.get(id=app_id)
    scheme = Scheme.objects.get(id=scheme_id)

    # Update application
    application.scheme = scheme
    application.status = 'Applied'
    application.applied_by = request.user
    application.application_number = f"APP-{application.id}-{scheme.id}"
    application.save()

    # Send notification
    Notification.objects.create(
        user=application.user,
        notification_type='email',
        subject=_('Scheme Applied'),
        message=_(f'We have applied for {scheme.scheme_name} on your behalf.')
    )

    messages.success(request, _('Scheme applied successfully!'))
    return redirect('admin_dashboard')


# -----------------------------
# REPORTS & ANALYTICS
# -----------------------------
@login_required
def reports(request):
    """Reports and analytics"""
    user_profile = UserProfile.objects.get(user=request.user)
    if user_profile.role not in ['volunteer', 'admin']:
        return redirect('dashboard')

    # Application status data
    status_data = list(
        ApplicationRequest.objects.values('status')
        .annotate(count=Count('status'))
    )

    # Scheme-wise applications
    scheme_data = list(
        ApplicationRequest.objects.filter(scheme__isnull=False)
        .values('scheme__scheme_name')
        .annotate(count=Count('scheme'))
        .order_by('-count')
    )

    # State-wise applications
    state_data = list(
        ApplicationRequest.objects.values('state')
        .annotate(count=Count('state'))
        .order_by('-count')
    )

    context = {
        'status_data': json.dumps(status_data),
        'scheme_data': json.dumps(scheme_data),
        'state_data': json.dumps(state_data),
    }
    return render(request, 'reports.html', context)


# -----------------------------
# LANGUAGE SWITCHER
# -----------------------------
def set_language(request):
    """Set user language preference"""
    lang_code = request.GET.get('lang', 'en')
    activate(lang_code)
    response = redirect(request.META.get('HTTP_REFERER', '/'))
    response.set_cookie('django_language', lang_code)
    return response


# -----------------------------
# DASHBOARD
# -----------------------------
@login_required
def dashboard(request):

    # 📊 APPLICATION STATISTICS (USER SPECIFIC)
    total_applications = ApplicationRequest.objects.filter(user=request.user).count()
    approved_apps = ApplicationRequest.objects.filter(user=request.user, status='Approved').count()
    pending_apps = ApplicationRequest.objects.filter(user=request.user, status='Pending').count()
    rejected_apps = ApplicationRequest.objects.filter(user=request.user, status='Rejected').count()

    # 📊 SCHEME STATISTICS (GLOBAL, since schemes are public)
    total_schemes = Scheme.objects.count()
    central_schemes = Scheme.objects.filter(scheme_type='Central').count()
    state_schemes = Scheme.objects.filter(scheme_type='State').count()

    # 📊 SCHEMES BY STATE (GLOBAL)
    schemes_by_state = list(
        Scheme.objects.values('state')
        .annotate(count=Count('state'))
        .order_by('-count')
    )

    # Calculate percentages for progress bars
    if schemes_by_state:
        max_count = schemes_by_state[0]['count']  # First item has the highest count
        for state in schemes_by_state:
            state['percentage'] = round((state['count'] / max_count) * 100) if max_count > 0 else 0

    # Calculate average schemes per state
    avg_per_state = round(total_schemes / len(schemes_by_state)) if schemes_by_state else 0

    # 📊 SCHEMES BY DEPARTMENT (GLOBAL)
    schemes_by_dept = list(
        Scheme.objects.values('department')
        .annotate(count=Count('department'))
        .order_by('-count')
    )

    # 📊 APPLICATION STATUS DATA (USER SPECIFIC)
    status_data = list(
        ApplicationRequest.objects.filter(user=request.user).values('status')
        .annotate(count=Count('status'))
    )

    # 📊 APPLICATIONS BY STATE (USER SPECIFIC)
    state_data = list(
        ApplicationRequest.objects.filter(user=request.user).values('state')
        .annotate(count=Count('state'))
        .order_by('-count')
    )

    # 📊 RECENT APPLICATIONS (USER SPECIFIC)
    recent_applications = ApplicationRequest.objects.filter(user=request.user).order_by('-created_at')[:5]

    # 📊 USER STATS (ALREADY USER SPECIFIC)
    user_applications = total_applications
    user_approved = approved_apps

    context = {
        'total_applications': total_applications,
        'approved_apps': approved_apps,
        'pending_apps': pending_apps,
        'rejected_apps': rejected_apps,
        'total_schemes': total_schemes,
        'central_schemes': central_schemes,
        'state_schemes': state_schemes,
        'user_applications': user_applications,
        'user_approved': user_approved,
        'status_data': json.dumps(status_data),
        'state_data': json.dumps(state_data),
        'schemes_by_state': schemes_by_state,
        'schemes_by_state_json': json.dumps(schemes_by_state),
        'schemes_by_dept': json.dumps(schemes_by_dept),
        'recent_applications': recent_applications,
        'avg_per_state': avg_per_state,
    }

    return render(request, 'dashboard.html', context)


def _format_link(url):
    if not url or not isinstance(url, str):
        return None
    clean_url = url.strip()
    if not clean_url:
        return None
    clean_url = clean_url.rstrip(' .,;\n\r\t')
    if clean_url.lower().startswith(('javascript:', 'data:', 'vbscript:')):
        return None
    if clean_url.startswith('//'):
        clean_url = 'https:' + clean_url
    if not clean_url.lower().startswith(('http://', 'https://')):
        clean_url = 'https://' + clean_url
    return clean_url


@login_required
def schemes_by_state_api(request, state_name):
    state_name_unescaped = state_name.replace('-', ' ')
    matching_schemes = Scheme.objects.filter(state__iexact=state_name_unescaped)
    if not matching_schemes.exists():
        raise Http404('No schemes found for state: %s' % state_name_unescaped)

    scheme_data = []
    for scheme in matching_schemes:
        official = _format_link(scheme.official_website)
        apply = _format_link(scheme.apply_link) or official
        scheme_data.append({
            'id': scheme.id,
            'scheme_name': scheme.scheme_name,
            'department': scheme.department,
            'scheme_type': scheme.scheme_type,
            'eligibility': scheme.eligibility,
            'description': scheme.description,
            'official_website': official,
            'apply_link': apply,
        })

    return JsonResponse({'state': state_name_unescaped, 'schemes': scheme_data})


# -----------------------------
# AI RECOMMENDATION
# -----------------------------
@login_required
def recommend_schemes(request):

    schemes = []
    form_data = {}

    if request.method == 'POST':
        age = int(request.POST.get('age'))
        income = int(request.POST.get('income'))
        category = request.POST.get('category')
        state = request.POST.get('state')

        form_data = {
            'age': age,
            'income': income,
            'category': category,
            'state': state
        }

        all_schemes = Scheme.objects.all()
        results = []

        for scheme in all_schemes:
            score = 0
            reasons = []

            # AGE CHECK
            if scheme.min_age <= age <= scheme.max_age:
                score += 40
                reasons.append("Age eligible")

            # INCOME CHECK
            if income <= scheme.income_limit:
                score += 30
                reasons.append("Income eligible")

            # CATEGORY CHECK
            if scheme.category == "All" or scheme.category == category:
                score += 20
                reasons.append("Category match")

            # STATE CHECK
            if state.lower() in scheme.state.lower():
                score += 10
                reasons.append("State match")

            scheme_official = _format_link(scheme.official_website)
            scheme_apply = _format_link(scheme.apply_link) or scheme_official

            results.append({
                'scheme': scheme,
                'score': score,
                'reasons': reasons,
                'official_url': scheme_official,
                'apply_url': scheme_apply
            })

        # SORT BY SCORE
        results = sorted(results, key=lambda x: x['score'], reverse=True)

        schemes = results[:5]   # TOP 5

    return render(request, 'recommend.html', {
        'schemes': schemes,
        'form_data': form_data
    })


# -----------------------------
# APPLY SCHEME
# -----------------------------
@login_required
def apply_scheme(request, scheme_id):

    scheme = Scheme.objects.get(id=scheme_id)

    ApplicationRequest.objects.create(
        user=request.user,
        scheme=scheme,
        name=request.user.username,
        age=25,
        gender="Male",
        mobile="9999999999",
        education="Graduate",
        income="300000",
        category="General",
        state=scheme.state,
        district="Unknown",
        status="Pending"
    )

    Notification.objects.create(
        user=request.user,
        message=f"You applied for {scheme.scheme_name}"
    )

    return redirect('/my-applications/')


# -----------------------------
# MY APPLICATIONS
# -----------------------------
@login_required
def my_applications(request):

    applications = ApplicationRequest.objects.filter(
        user=request.user
    ).order_by('-created_at')

    return render(request, 'my_applications.html', {
        'applications': applications
    })


import openai
from django.conf import settings

openai.api_key = getattr(settings, 'OPENAI_API_KEY', None)

def default_chatbot_response(message):
    message_low = (message or '').lower()

    if not message_low.strip():
        return "Please ask a question about schemes, e.g., age income state."

    # Simple keyword reply
    if 'kisan' in message_low:
        return "PM Kisan gives ₹6000 per year for small and marginal farmers."
    if 'insurance' in message_low or 'bima' in message_low:
        return "Crop insurance is available under Pradhan Mantri Fasal Bima Yojana."
    if 'hello' in message_low or 'hi' in message_low:
        return "Hi! Provide age, income and state to get scheme recommendations."

    # Extract basic age/income/state for fallback recommendation
    import re
    age = None
    income = None
    state = ''
    numbers = re.findall(r'\d+', message_low)
    if len(numbers) >= 1:
        age = int(numbers[0])
    if len(numbers) >= 2:
        income = int(numbers[1])

    states = ["maharashtra", "tamil nadu", "kerala", "karnataka", "delhi", "telangana", "rajasthan"]
    for s in states:
        if s in message_low:
            state = s

    if age and income:
        schemes = Scheme.objects.all()
        matched = []
        for scheme in schemes:
            score = 0
            if scheme.min_age <= age <= scheme.max_age:
                score += 40
            if income <= scheme.income_limit:
                score += 30
            if state and state in scheme.state.lower():
                score += 30
            if score >= 60:
                matched.append((scheme.scheme_name, score))
        matched = sorted(matched, key=lambda x: x[1], reverse=True)
        if matched:
            names = [m[0] for m in matched[:3]]
            return f"🎯 Best schemes: {', '.join(names)}"
        return "No matching schemes found, please try different values."

    return "Sorry, I didn't understand that. Ask about age, income, state or scheme names."


def chatbot(request):
    message = request.GET.get('message', '').strip()
    mode = request.GET.get('mode', 'auto').lower()

    if not message:
        return JsonResponse({'reply': "Please type your query in chat."})

    def get_local_response():
        return default_chatbot_response(message)

    if mode == 'local':
        reply = get_local_response()
    elif mode == 'openai':
        if openai.api_key:
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an AI assistant for Indian agricultural schemes."},
                        {"role": "user", "content": message}
                    ],
                    temperature=0.7,
                    max_tokens=160
                )
                reply = response['choices'][0]['message']['content'].strip()
                if not reply:
                    reply = get_local_response()
            except Exception as e:
                print('OpenAI error:', e)
                reply = get_local_response()
        else:
            reply = "OpenAI API key is not configured. Please switch to Local mode." 
    else:
        # auto mode: prefer OpenAI if available
        if openai.api_key:
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an AI assistant for Indian agricultural schemes."},
                        {"role": "user", "content": message}
                    ],
                    temperature=0.7,
                    max_tokens=160
                )
                reply = response['choices'][0]['message']['content'].strip()
                if not reply:
                    reply = get_local_response()
            except Exception as e:
                print('OpenAI error:', e)
                reply = get_local_response()
        else:
            reply = get_local_response()

    return JsonResponse({'reply': reply})