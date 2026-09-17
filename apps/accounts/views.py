from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from apps.audit.utils import record_audit_event


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            record_audit_event(
                user=user,
                event_type='user.register',
                request=request,
                metadata={'username': user.username, 'email': user.email}
            )
            login(request, user)
            messages.success(request, f"Welcome to YouTube Shorts Converter, {user.username}!")
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            record_audit_event(
                user=user,
                event_type='user.login',
                request=request,
                metadata={'username': user.username}
            )
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.GET.get('next') or 'dashboard'
            return redirect(next_url)
    else:
        form = CustomAuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    record_audit_event(
        user=request.user,
        event_type='user.logout',
        request=request,
        metadata={'username': request.user.username}
    )
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('home')


@login_required
def profile_view(request):
    profile = request.user.profile
    recent_audits = request.user.audit_events.order_by('-created_at')[:20]
    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'recent_audits': recent_audits,
    })
