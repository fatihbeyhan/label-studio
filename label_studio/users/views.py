"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license.
"""
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.shortcuts import render, redirect, reverse
from django.contrib import auth
from django.conf import settings
from rest_framework.authtoken.models import Token

from users import forms
from core.permissions import view_with_auth, IsBusiness
from organizations.models import Organization
from organizations.forms import OrganizationSignupForm


logger = logging.getLogger()


class FPasswordResetView(auth_views.PasswordResetView):
    from_email = 'info@labelstud.io'
    template_name = 'password/password_reset_form.html'


class FPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'password/password_reset_done.html'


class FPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'password/password_reset_confirm.html'


class FPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'password/password_reset_complete.html'


@login_required
def logout(request):
    auth.logout(request)
    return redirect('/')


def save_user(request, *args):
    """ Save user instance to DB
    """
    next_page, user_form, organization_form = args

    user = user_form.save()
    user.username = user.email.split('@')[0]
    user.save()

    redirect_url = next_page if next_page else reverse('projects:project-index')
    auth.login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return user, redirect_url


def proceed_registration(request, user_form, organization_form, next_page):
    """ Register a new user for POST user_signup
    """
    # save user to db
    user, redirect_url = save_user(request, next_page, user_form, organization_form)

    if Organization.objects.exists():
        org = Organization.objects.first()
        org.add_user(user)
    else:
        org = Organization.create_organization(created_by=user, title='Label Studio')
    request.session['organization_pk'] = org.pk
    request.session.modified = True

    return redirect(redirect_url)


def user_signup(request):
    """ Sign up page
    """
    user = request.user
    next_page = request.GET.get('next')
    next_page = next_page if next_page else reverse('projects:project-index')
    user_form = forms.UserSignupForm()
    organization_form = OrganizationSignupForm()

    if user.is_authenticated:
        return redirect(next_page)

    # make a new user
    if request.method == 'POST':
        user_form = forms.UserSignupForm(request.POST)
        organization_form = OrganizationSignupForm(request.POST)

        if user_form.is_valid():
            redirect_response = proceed_registration(request, user_form, organization_form, next_page)
            if redirect_response:
                return redirect_response

    return render(request, 'users/user_signup.html', {
        'user_form': user_form,
        'organization_form': organization_form,
        'next': next_page
    })


def user_login(request):
    """ Login page
    """
    user = request.user
    next_page = request.GET.get('next')
    next_page = next_page if next_page else reverse('projects:project-index')
    form = forms.LoginForm()

    if user.is_authenticated:
        return redirect(next_page)

    if request.method == 'POST':
        form = forms.LoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            auth.login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            # user is organization member
            org_pk = Organization.find_by_user(user).pk
            request.session['organization_pk'] = org_pk
            request.session.modified = True
            return redirect(next_page)

    return render(request, 'users/user_login.html', {
        'form': form,
        'next': next_page
    })


@view_with_auth(['GET', 'POST'], (IsBusiness,))
def user_account(request):
    user = request.user

    if 'organization_pk' not in request.session:
        return redirect(reverse('main'))

    form = forms.UserProfileForm(instance=user)
    token = Token.objects.get(user=user)

    if request.method == 'POST':
        form = forms.UserProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect(reverse('user-account'))

    return render(request, 'users/user_account.html', {
        'settings': settings,
        'user': user,
        'user_profile_form': form,
        'token': token
    })
