from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout as auth_logout
from django.http import JsonResponse, Http404, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext as _, activate, check_for_language
from django.urls import translate_url
from django.conf import settings as conf_settings
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlparse, urlencode
from urllib.request import Request, urlopen
from .models import ApplicationRequest, Scheme, Notification, UserProfile
from .forms import UserRegisterForm, UserUpdateForm, UserProfileForm, CitizenApplicationForm, SchemeForm
import csv
import json
import re
import os
import tempfile
import subprocess


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


def logout_user(request):
    """Log out current user and redirect to home."""
    auth_logout(request)
    messages.success(request, _('You have been logged out successfully.'))
    return redirect('home')


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


def scheme_awareness(request):
    """Public scheme listing with filters, stats, and search."""
    all_schemes = Scheme.objects.all()
    schemes = all_schemes

    search_query = (request.GET.get('q') or '').strip()
    state_filter = (request.GET.get('state') or '').strip()
    category_filter = (request.GET.get('category') or '').strip()
    type_filter = (request.GET.get('type') or '').strip()

    if search_query:
        schemes = schemes.filter(
            Q(scheme_name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category__icontains=search_query)
            | Q(department__icontains=search_query)
        )

    if state_filter:
        schemes = schemes.filter(state__iexact=state_filter)

    if category_filter:
        schemes = schemes.filter(category__iexact=category_filter)

    if type_filter in ['Central', 'State']:
        schemes = schemes.filter(scheme_type=type_filter)

    states = list(
        all_schemes.exclude(state__isnull=True)
        .exclude(state__exact='')
        .values_list('state', flat=True)
        .distinct()
        .order_by('state')
    )

    categories = list(
        all_schemes.exclude(category__isnull=True)
        .exclude(category__exact='')
        .values_list('category', flat=True)
        .distinct()
        .order_by('category')
    )

    context = {
        'schemes': schemes.order_by('scheme_name'),
        'total_schemes': all_schemes.count(),
        'central_schemes': all_schemes.filter(scheme_type='Central').count(),
        'state_schemes': all_schemes.filter(scheme_type='State').count(),
        'states': states,
        'categories': categories,
        'search_query': search_query,
        'state_filter': state_filter,
        'category_filter': category_filter,
        'type_filter': type_filter,
    }
    return render(request, 'scheme_awareness.html', context)


def india_map_schemes(request):
    """Render the interactive India scheme map dashboard."""
    return render(request, 'india_map_schemes.html')


def state_dashboard(request, state_name):
    """Render the state-specific analytics dashboard."""
    return render(request, 'state_dashboard.html', {'state_name': state_name})


def scheme_detail(request, scheme_id):
    """Public scheme detail page. Apply action remains login-protected."""
    scheme = get_object_or_404(Scheme, id=scheme_id)
    return render(request, 'scheme_detail.html', {'scheme': scheme})


def tts_proxy(request):
    """Proxy Google Translate TTS audio to avoid browser CORS restrictions."""
    text = (request.GET.get('text') or '').strip()
    language = (request.GET.get('lang') or 'en').strip()

    if not text:
        return HttpResponse('Text parameter is required.', status=400)

    language_map = {
        'English': 'en',
        'Hindi': 'hi',
        'Marathi': 'mr',
        'Telugu': 'te',
        'Tamil': 'ta',
        'Kannada': 'kn',
        'Malayalam': 'ml',
        'Bengali': 'bn',
        'Gujarati': 'gu',
        'Punjabi': 'pa'
    }

    code = language_map.get(language, language if len(language) == 2 else 'en')
    params = urlencode({'ie': 'UTF-8', 'tl': code, 'client': 'tw-ob', 'q': text})
    url = f'https://translate.google.com/translate_tts?{params}'

    req = Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36'
    })

    try:
        with urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get_content_type() if hasattr(resp.headers, 'get_content_type') else 'audio/mpeg'
            return HttpResponse(resp.read(), content_type=content_type)
    except Exception as exc:
        return HttpResponse(f'TTS proxy error: {exc}', status=502)


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
    user_profile = get_object_or_404(UserProfile, user=request.user)
    if user_profile.role not in ['volunteer', 'admin']:
        return redirect('dashboard')

    application = get_object_or_404(ApplicationRequest, id=app_id)

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
    user_profile = get_object_or_404(UserProfile, user=request.user)
    if user_profile.role not in ['volunteer', 'admin']:
        return redirect('dashboard')

    application = get_object_or_404(ApplicationRequest, id=app_id)
    scheme = get_object_or_404(Scheme, id=scheme_id)

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
    user_profile = get_object_or_404(UserProfile, user=request.user)
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
    """Set user language preference and redirect to language-prefixed URL."""
    lang_code = request.GET.get('lang') or request.POST.get('lang') or 'en'
    valid_codes = {code for code, _ in conf_settings.LANGUAGES}
    if lang_code not in valid_codes:
        lang_code = 'en'

    activate(lang_code)

    # Prefer explicit next target, otherwise fall back to referrer.
    next_url = request.GET.get('next') or request.POST.get('next') or request.META.get('HTTP_REFERER', '/')

    # Prevent open redirects.
    if not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = '/'

    parsed = urlparse(next_url)
    path_only = parsed.path or '/'
    query = f'?{parsed.query}' if parsed.query else ''

    # Strip any existing language prefix so we never double-prefix.
    all_lang_codes = [code for code, _ in conf_settings.LANGUAGES if code != 'en']
    for code in all_lang_codes:
        if path_only.startswith(f'/{code}/'):
            path_only = path_only[len(code) + 1:]  # strip /code, keep leading /
            break
        if path_only == f'/{code}':
            path_only = '/'
            break

    # Build language-prefixed path directly.
    # English uses no prefix (prefix_default_language=False in i18n_patterns).
    if lang_code == 'en':
        next_path = path_only + query
    else:
        next_path = f'/{lang_code}{path_only}' + query

    response = redirect(next_path)
    
    # Store language in session so LocaleMiddleware can find it immediately
    if hasattr(request, 'session'):
        request.session['_language'] = lang_code
        request.session.modified = True
    
    # Also set language cookie for persistence
    response.set_cookie(
        conf_settings.LANGUAGE_COOKIE_NAME,
        lang_code,
        max_age=getattr(conf_settings, 'LANGUAGE_COOKIE_AGE', 365 * 24 * 60 * 60),
        path=getattr(conf_settings, 'LANGUAGE_COOKIE_PATH', '/'),
        secure=getattr(conf_settings, 'LANGUAGE_COOKIE_SECURE', False),
        httponly=getattr(conf_settings, 'LANGUAGE_COOKIE_HTTPONLY', False),
        samesite=getattr(conf_settings, 'LANGUAGE_COOKIE_SAMESITE', 'Lax'),
    )
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


def _normalize_state_name(name):
    if not name:
        return ''
    return name.replace('-', ' ').strip().lower()


def _bucket_scheme_category(row):
    category_text = (row.get('department') or row.get('scheme_type') or '').strip().lower()
    if not category_text:
        return 'Other'
    if 'agri' in category_text or 'farm' in category_text:
        return 'Agriculture'
    if 'health' in category_text or 'medical' in category_text or 'care' in category_text:
        return 'Healthcare'
    if 'educ' in category_text or 'skill' in category_text or 'school' in category_text:
        return 'Education'
    if 'women' in category_text:
        return 'Women Empowerment'
    if 'social' in category_text or 'welfare' in category_text or 'poverty' in category_text:
        return 'Social Welfare'
    if 'econom' in category_text or 'loan' in category_text or 'finance' in category_text or 'credit' in category_text:
        return 'Economic Support'
    return category_text.title()


def india_map_overview_api(request):
    csv_path = os.path.join(conf_settings.BASE_DIR, 'schemes_data.csv')
    if not os.path.exists(csv_path):
        csv_path = os.path.join(conf_settings.BASE_DIR, 'schemes.csv')

    all_schemes = _load_schemes_from_csv(csv_path)
    total_schemes = len(all_schemes)
    central_schemes = sum(1 for scheme in all_schemes if (scheme.get('scheme_type') or '').strip().lower() == 'central')
    state_schemes = total_schemes - central_schemes

    category_counts = {}
    state_counts = {}
    for scheme in all_schemes:
        bucket = _bucket_scheme_category(scheme)
        category_counts[bucket] = category_counts.get(bucket, 0) + 1
        state_name = (scheme.get('state') or '').strip()
        if state_name and state_name.lower() != 'india':
            state_counts[state_name] = state_counts.get(state_name, 0) + 1

    top_states = sorted(state_counts.items(), key=lambda item: item[1], reverse=True)[:8]
    top_category = max(category_counts.items(), key=lambda item: item[1])[0] if category_counts else 'General'

    return JsonResponse({
        'total_schemes': total_schemes,
        'central_schemes': central_schemes,
        'state_schemes': state_schemes,
        'category_counts': category_counts,
        'top_states': [{'state': name, 'count': count} for name, count in top_states],
        'top_category': top_category,
    })


def india_map_state_analytics_api(request, state_name):
    requested_state = _normalize_state_name(state_name)
    csv_path = os.path.join(conf_settings.BASE_DIR, 'schemes_data.csv')
    if not os.path.exists(csv_path):
        csv_path = os.path.join(conf_settings.BASE_DIR, 'schemes.csv')

    all_schemes = _load_schemes_from_csv(csv_path)
    matching_schemes = []
    for scheme in all_schemes:
        scheme_state = _normalize_state_name(scheme.get('state'))
        is_central = (scheme.get('scheme_type') or '').strip().lower() == 'central'
        if is_central or scheme_state == requested_state:
            matching_schemes.append(scheme)

    total_schemes = len(matching_schemes)
    central_schemes = sum(1 for scheme in matching_schemes if (scheme.get('scheme_type') or '').strip().lower() == 'central')
    state_schemes = total_schemes - central_schemes
    category_counts = {}
    for scheme in matching_schemes:
        bucket = _bucket_scheme_category(scheme)
        category_counts[bucket] = category_counts.get(bucket, 0) + 1

    top_category = max(category_counts.items(), key=lambda item: item[1])[0] if category_counts else 'General'
    top_categories = sorted(category_counts.items(), key=lambda item: item[1], reverse=True)

    return JsonResponse({
        'state_name': state_name,
        'total_schemes': total_schemes,
        'central_schemes': central_schemes,
        'state_schemes': state_schemes,
        'category_counts': category_counts,
        'top_category': top_category,
        'top_categories': [{ 'category': key, 'count': value } for key, value in top_categories],
    })


def _load_schemes_from_csv(csv_path):
    schemes = []
    if not os.path.exists(csv_path):
        return schemes

    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            schemes.append({
                'id': (row.get('id') or '').strip(),
                'scheme_name': (row.get('scheme_name') or '').strip(),
                'description': (row.get('description') or '').strip(),
                'eligibility': (row.get('eligibility') or '').strip(),
                'documents_required': (row.get('documents_required') or '').strip(),
                'official_website': (row.get('official_website') or '').strip(),
                'state': (row.get('state') or '').strip(),
                'scheme_type': (row.get('scheme_type') or '').strip(),
                'department': (row.get('department') or '').strip(),
            })
    return schemes


def schemes_by_state_api(request, state_name):
    requested_state = state_name.replace('-', ' ').strip()
    csv_path = os.path.join(conf_settings.BASE_DIR, 'schemes_data.csv')
    if not os.path.exists(csv_path):
        csv_path = os.path.join(conf_settings.BASE_DIR, 'schemes.csv')

    all_schemes = _load_schemes_from_csv(csv_path)
    matching = []
    for scheme in all_schemes:
        row_state = scheme.get('state', '').strip()
        is_central = scheme.get('scheme_type', '').lower() == 'central'
        if is_central or row_state.lower() == requested_state.lower():
            matching.append({
                'id': scheme.get('id'),
                'name': scheme.get('scheme_name'),
                'description': scheme.get('description'),
                'eligibility': scheme.get('eligibility'),
                'documents_required': scheme.get('documents_required'),
                'category': scheme.get('scheme_type') or 'General',
                'apply_link': scheme.get('official_website'),
                'official_website': scheme.get('official_website'),
                'department': scheme.get('department'),
                'state': row_state,
            })

    return JsonResponse(matching, safe=False)


def state_schemes_public_api(request, state_name):
    """Public API endpoint returning a JSON array of schemes for a selected state."""
    state_name_unescaped = state_name.replace('-', ' ')
    # Get both state-specific schemes and central schemes
    matching_schemes = Scheme.objects.filter(
        Q(state__iexact=state_name_unescaped) | Q(scheme_type='Central')
    ).order_by('scheme_name')

    if not matching_schemes.exists():
        return JsonResponse([], safe=False, status=404)

    scheme_data = []
    for scheme in matching_schemes:
        apply_link = _format_link(scheme.apply_link) or _format_link(scheme.official_website)
        scheme_data.append({
            'name': scheme.scheme_name,
            'description': scheme.description or scheme.benefits or 'No description available.',
            'category': scheme.category or scheme.scheme_type or 'General',
            'apply_link': apply_link,
            'official_website': _format_link(scheme.official_website),
            'id': scheme.id,
        })

    return JsonResponse(scheme_data, safe=False)


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

    scheme = get_object_or_404(Scheme, id=scheme_id)

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
    messages.success(request, _(f"Application recorded for {scheme.scheme_name}. Redirecting to the official portal…"))

    # Prefer the dedicated apply link, fall back to official website.
    # Normalize before redirecting so links without protocol do not break.
    external_url = _format_link(scheme.apply_link) or _format_link(scheme.official_website)
    if external_url:
        return redirect(external_url)

    messages.warning(request, _('Official website link is unavailable for this scheme.'))
    return redirect('my_apps')


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


def _get_openai_client():
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        return None

    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def _normalize_lang_code(raw_lang):
    lang = (raw_lang or 'auto').lower().strip()
    if lang in ['hi', 'hi-in', 'hindi']:
        return 'hi'
    if lang in ['mr', 'mr-in', 'marathi']:
        return 'mr'
    if lang in ['en', 'en-in', 'english']:
        return 'en'
    return 'auto'


def _detect_reply_language(message, requested_lang='auto'):
    lang = _normalize_lang_code(requested_lang)
    if lang != 'auto':
        return lang

    text = (message or '').strip()
    if not text:
        return 'en'

    if re.search(r'[\u0900-\u097F]', text):
        marathi_markers = ['मला', 'आहे', 'योजना', 'शेतकरी', 'काय', 'माझ्या', 'साठी']
        text_low = text.lower()
        if any(marker in text_low for marker in marathi_markers):
            return 'mr'
        return 'hi'

    return 'en'


def _localize_text(key, lang='en'):
    messages = {
        'ask_question': {
            'en': 'Please ask a question about schemes, such as age, income, and state.',
            'hi': 'कृपया योजना के बारे में प्रश्न पूछें, जैसे उम्र, आय और राज्य।',
            'mr': 'कृपया योजनांबद्दल प्रश्न विचारा, जसे वय, उत्पन्न आणि राज्य.'
        },
        'hello': {
            'en': 'Hi! Share your age, income, and state to get better scheme recommendations.',
            'hi': 'नमस्ते! बेहतर योजना सुझाव पाने के लिए अपनी उम्र, आय और राज्य बताएं।',
            'mr': 'नमस्कार! चांगल्या योजना शिफारसींसाठी तुमचे वय, उत्पन्न आणि राज्य सांगा.'
        },
        'no_match': {
            'en': 'I could not find an exact scheme match yet. Please share age, annual income, category, and state.',
            'hi': 'मुझे अभी सटीक योजना मिलान नहीं मिला। कृपया उम्र, वार्षिक आय, श्रेणी और राज्य बताएं।',
            'mr': 'मला अजून अचूक योजना जुळणी मिळाली नाही. कृपया वय, वार्षिक उत्पन्न, प्रवर्ग आणि राज्य सांगा.'
        },
        'top_options': {
            'en': 'Here are the best options for your query:',
            'hi': 'आपके प्रश्न के लिए सबसे उपयुक्त विकल्प:',
            'mr': 'तुमच्या प्रश्नासाठी सर्वोत्तम पर्याय:'
        },
        'kisan': {
            'en': 'PM Kisan provides Rs. 6000 per year to eligible small and marginal farmers.',
            'hi': 'पीएम किसान योजना पात्र छोटे और सीमांत किसानों को प्रति वर्ष ₹6000 देती है।',
            'mr': 'पीएम किसान योजनेत पात्र लघु आणि सीमांत शेतकऱ्यांना दरवर्षी ₹6000 मिळतात.'
        },
        'insurance': {
            'en': 'Crop insurance support is available under Pradhan Mantri Fasal Bima Yojana.',
            'hi': 'फसल बीमा सहायता प्रधानमंत्री फसल बीमा योजना के तहत उपलब्ध है।',
            'mr': 'प्रधानमंत्री फसल विमा योजनेअंतर्गत पीक विमा मदत उपलब्ध आहे.'
        },
    }
    return messages.get(key, {}).get(lang, messages.get(key, {}).get('en', ''))


def _transcribe_audio_with_openai(audio_file):
    """Return transcript text using Whisper when API key is configured."""
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        return ''

    # New SDK path
    client = _get_openai_client()
    if client:
        try:
            content_type = getattr(audio_file, 'content_type', None) or 'audio/webm'
            transcript = client.audio.transcriptions.create(
                model='whisper-1',
                file=(getattr(audio_file, 'name', 'voice.webm'), audio_file, content_type),
            )
            text = getattr(transcript, 'text', '') or ''
            if text:
                return text.strip()
        except Exception:
            try:
                audio_file.seek(0)
            except Exception:
                pass

    # Legacy SDK path
    try:
        transcript = openai.Audio.transcribe('whisper-1', audio_file)
        text = transcript.get('text', '') if isinstance(transcript, dict) else ''
        return (text or '').strip()
    except Exception:
        return ''


def _transcribe_audio_without_openai(audio_file, language='auto'):
    """Fallback STT using SpeechRecognition + ffmpeg conversion when needed."""
    try:
        import speech_recognition as sr
    except Exception:
        return '', 'SpeechRecognition library not installed on server.'

    try:
        import imageio_ffmpeg
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_bin = 'ffmpeg'

    requested_lang = _normalize_lang_code(language)
    locale = {
        'hi': 'hi-IN',
        'mr': 'mr-IN',
        'en': 'en-IN',
        'auto': 'hi-IN',
    }[requested_lang]

    recognizer = sr.Recognizer()
    suffix = os.path.splitext(getattr(audio_file, 'name', 'voice.webm'))[1] or '.webm'

    tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_in.write(audio_file.read())
    tmp_in.flush()
    tmp_in_path = tmp_in.name
    tmp_in.close()

    tmp_wav_path = tempfile.NamedTemporaryFile(delete=False, suffix='.wav').name

    try:
        input_ext = suffix.lower()
        source_path = tmp_in_path

        # WAV/AIFF/FLAC can be parsed directly by SpeechRecognition.
        if input_ext not in ['.wav', '.aiff', '.aif', '.flac']:
            cmd = [
                ffmpeg_bin, '-y', '-i', tmp_in_path,
                '-ac', '1', '-ar', '16000', '-f', 'wav', tmp_wav_path
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if proc.returncode != 0:
                return '', 'Audio conversion failed on server. Please try again with a clear 5-6 second recording.'
            source_path = tmp_wav_path

        with sr.AudioFile(source_path) as source:
            audio_data = recognizer.record(source)

        text = recognizer.recognize_google(audio_data, language=locale)
        return (text or '').strip(), ''
    except sr.UnknownValueError:
        return '', 'Could not understand the recorded audio. Please speak clearly and retry.'
    except sr.RequestError:
        return '', 'Speech service is unavailable from server right now. Please try again in a minute.'
    except Exception:
        return '', 'Server fallback transcription failed due to an internal error.'
    finally:
        for path in [tmp_in_path, tmp_wav_path]:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass


def _extract_profile_from_message(message):
    message_low = (message or '').lower()
    age = None
    income = None
    state = ''

    numbers = re.findall(r'\d+', message_low)
    if len(numbers) >= 1:
        age = int(numbers[0])
    if len(numbers) >= 2:
        income = int(numbers[1])

    states = [
        'maharashtra', 'tamil nadu', 'kerala', 'karnataka', 'delhi', 'telangana',
        'rajasthan', 'uttar pradesh', 'madhya pradesh', 'west bengal', 'gujarat',
        'punjab', 'haryana', 'bihar', 'odisha', 'andhra pradesh', 'assam'
    ]
    for s in states:
        if s in message_low:
            state = s
            break

    return age, income, state


def _find_matching_schemes(age=None, income=None, state='', category='All', query=''):
    schemes = Scheme.objects.all()
    matched = []
    query_low = (query or '').lower().strip()

    for scheme in schemes:
        score = 0
        reasons = []

        if age is not None and scheme.min_age <= age <= scheme.max_age:
            score += 35
            reasons.append('age eligibility')

        if income is not None and income <= scheme.income_limit:
            score += 30
            reasons.append('income eligibility')

        if state and state in (scheme.state or '').lower():
            score += 20
            reasons.append('state match')

        if category and category != 'All' and (scheme.category == 'All' or scheme.category == category):
            score += 10
            reasons.append('category match')

        if query_low:
            haystack = ' '.join([
                scheme.scheme_name or '',
                scheme.description or '',
                scheme.eligibility or '',
                scheme.department or '',
                scheme.state or '',
            ]).lower()
            if any(token in haystack for token in query_low.split() if len(token) > 2):
                score += 25
                reasons.append('query relevance')

        if score > 0:
            matched.append((scheme, score, reasons))

    matched.sort(key=lambda item: item[1], reverse=True)
    return matched[:5]


def default_chatbot_response(message):
    lang = _detect_reply_language(message)
    message_low = (message or '').lower()

    if not message_low.strip():
        return _localize_text('ask_question', lang)

    # Friendly quick replies
    if 'kisan' in message_low:
        return _localize_text('kisan', lang)
    if 'insurance' in message_low or 'bima' in message_low:
        return _localize_text('insurance', lang)
    if 'hello' in message_low or 'hi' in message_low:
        return _localize_text('hello', lang)

    age, income, state = _extract_profile_from_message(message)
    matched = _find_matching_schemes(age=age, income=income, state=state, query=message)

    if matched:
        lines = []
        for scheme, score, reasons in matched[:3]:
            reason_text = ', '.join(reasons[:2]) if reasons else 'general relevance'
            if lang == 'hi':
                lines.append(f"- {scheme.scheme_name} ({scheme.state}) - स्कोर {score} ({reason_text})")
            elif lang == 'mr':
                lines.append(f"- {scheme.scheme_name} ({scheme.state}) - गुण {score} ({reason_text})")
            else:
                lines.append(f"- {scheme.scheme_name} ({scheme.state}) - match score {score} ({reason_text})")
        return _localize_text('top_options', lang) + "\n" + "\n".join(lines)

    return _localize_text('no_match', lang)


@login_required
@require_POST
def transcribe_voice(request):
    audio_file = request.FILES.get('audio')
    language = request.POST.get('language', 'auto')
    if not audio_file:
        return JsonResponse({'error': 'Audio file is required.'}, status=400)

    if audio_file.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'Audio file too large. Please keep it under 10MB.'}, status=400)

    transcript = _transcribe_audio_with_openai(audio_file)
    if not transcript:
        try:
            audio_file.seek(0)
        except Exception:
            pass
        transcript, fallback_error = _transcribe_audio_without_openai(audio_file, language=language)

    if not transcript:
        return JsonResponse({
            'error': fallback_error or 'Unable to transcribe audio. Configure OPENAI_API_KEY or install fallback STT dependencies.'
        }, status=502)

    return JsonResponse({'transcript': transcript})


def _stream_text_chunks(text):
    if not text:
        return
    for token in text.split():
        payload = json.dumps({'token': token + ' '})
        yield f"data: {payload}\n\n"
    yield "data: {\"done\": true}\n\n"


def _build_openai_messages(message, response_lang):
    language_hint = {
        'hi': 'Reply in Hindi.',
        'mr': 'Reply in Marathi.',
        'en': 'Reply in English.',
        'auto': 'Reply in the user language.',
    }.get(response_lang, 'Reply in the user language.')

    top_matches = _find_matching_schemes(query=message)
    context_lines = []
    for scheme, score, _ in top_matches[:3]:
        context_lines.append(
            f"{scheme.scheme_name} | {scheme.state} | {scheme.category} | income_limit={scheme.income_limit}"
        )

    return [
        {
            'role': 'system',
            'content': 'You are SmartAssist, an assistant for Indian farmer welfare schemes. Give concise, practical answers.'
        },
        {
            'role': 'system',
            'content': language_hint
        },
        {
            'role': 'system',
            'content': 'Relevant scheme context:\n' + '\n'.join(context_lines) if context_lines else 'No specific context found.'
        },
        {
            'role': 'user',
            'content': message
        }
    ]


def chatbot(request):
    message = request.GET.get('message', '').strip()
    mode = request.GET.get('mode', 'auto').lower()
    requested_lang = request.GET.get('lang', 'auto')
    response_lang = _detect_reply_language(message, requested_lang)

    if not message:
        return JsonResponse({'reply': _localize_text('ask_question', response_lang)})

    def get_local_response():
        return default_chatbot_response(message)

    if mode == 'local':
        reply = get_local_response()
    elif mode == 'openai':
        client = _get_openai_client()
        if client:
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=_build_openai_messages(message, response_lang),
                    temperature=0.7,
                    max_tokens=220
                )
                reply = (response.choices[0].message.content or '').strip()
                if not reply:
                    reply = get_local_response()
            except Exception:
                reply = get_local_response()
        else:
            reply = "OpenAI API key is not configured. Please switch to Local mode." 
    else:
        # auto mode: prefer OpenAI if available
        client = _get_openai_client()
        if client:
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=_build_openai_messages(message, response_lang),
                    temperature=0.7,
                    max_tokens=220
                )
                reply = (response.choices[0].message.content or '').strip()
                if not reply:
                    reply = get_local_response()
            except Exception:
                reply = get_local_response()
        else:
            reply = get_local_response()

    return JsonResponse({'reply': reply})


def chatbot_stream(request):
    message = request.GET.get('message', '').strip()
    mode = request.GET.get('mode', 'auto').lower()
    requested_lang = request.GET.get('lang', 'auto')
    response_lang = _detect_reply_language(message, requested_lang)

    if not message:
        def empty_stream():
            for chunk in _stream_text_chunks(_localize_text('ask_question', response_lang)):
                yield chunk
        return StreamingHttpResponse(empty_stream(), content_type='text/event-stream')

    def event_stream():
        local_reply = default_chatbot_response(message)

        if mode in ['openai', 'auto']:
            client = _get_openai_client()
            if client:
                try:
                    stream = client.chat.completions.create(
                        model='gpt-4o-mini',
                        messages=_build_openai_messages(message, response_lang),
                        temperature=0.7,
                        max_tokens=220,
                        stream=True,
                    )

                    sent_any = False
                    for part in stream:
                        delta = ''
                        try:
                            delta = part.choices[0].delta.content or ''
                        except Exception:
                            delta = ''

                        if delta:
                            sent_any = True
                            yield f"data: {json.dumps({'token': delta})}\n\n"

                    if not sent_any:
                        for chunk in _stream_text_chunks(local_reply):
                            yield chunk
                    else:
                        yield "data: {\"done\": true}\n\n"
                    return
                except Exception:
                    pass

        for chunk in _stream_text_chunks(local_reply):
            yield chunk

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response