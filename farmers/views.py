from django.shortcuts import render
from django.db.models import Count
from .models import ApplicationRequest, Scheme
import json

def dashboard(request):

    total_applications = ApplicationRequest.objects.count()

    # STATUS DATA
    status_data = list(
        ApplicationRequest.objects.values('status')
        .annotate(count=Count('status'))
    )

    # STATE DATA
    state_data = list(
        ApplicationRequest.objects.values('state')
        .annotate(count=Count('state'))
    )

    context = {
        'total_applications': total_applications,
        'status_data': json.dumps(status_data),
        'state_data': json.dumps(state_data),
    }

    return render(request, 'dashboard.html', context)

def recommend_schemes(request):
    schemes = None
    form_data = {}

    if request.method == 'POST':
        age = int(request.POST.get('age', 0))
        income = int(request.POST.get('income', 0))
        category = request.POST.get('category', '')
        state = request.POST.get('state', '')

        form_data = {
            'age': age,
            'income': income,
            'category': category,
            'state': state,
        }

        # Filter schemes based on criteria
        schemes = Scheme.objects.filter(
            min_age__lte=age,
            max_age__gte=age,
            income_limit__gte=income,
            state__icontains=state
        )

        # If category is specified and not "General", filter by category
        if category and category != "General":
            schemes = schemes.filter(category__icontains=category)

    context = {
        'schemes': schemes,
        'form_data': form_data,
    }

    return render(request, 'recommend.html', context)


from django.shortcuts import render
from .models import Scheme

def recommend_schemes(request):

    schemes = []
    form_data = {}

    if request.method == 'POST':
        age = request.POST.get('age')
        income = request.POST.get('income')
        category = request.POST.get('category')
        state = request.POST.get('state')

        form_data = {
            'age': age,
            'income': income,
            'category': category,
            'state': state
        }

        if age and income and state:
            schemes = Scheme.objects.filter(
                min_age__lte=int(age),
                max_age__gte=int(age),
                income_limit__gte=int(income),
            )

            # 🔥 Smart state handling
            if state.lower() != "india":
                schemes = schemes.filter(state__icontains=state) | schemes.filter(state__icontains="India")
            
            if category and category != "General":
                schemes = schemes.filter(category__icontains=category)

    return render(request, 'recommend.html', {
        'schemes': schemes,
        'form_data': form_data
    })