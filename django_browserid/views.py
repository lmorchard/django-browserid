from django.conf import settings
from django.contrib import auth
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_POST

from django_browserid.forms import BrowserIDForm


def _get_host_and_port(request):
    """Return host, port if port is nonstandard or host, '80' otherwise"""
    host = request.get_host()
    return ':' in host and host.split(':') or (host, '80')


@require_POST
def verify(request, redirect_field_name=auth.REDIRECT_FIELD_NAME):
    """Process browserid assertions."""
    redirect_to = request.REQUEST.get(redirect_field_name, '')
    if not redirect_to:
        redirect_to = getattr(settings, 'LOGIN_REDIRECT_URL', '/')
    redirect_to_failure = getattr(settings, 'LOGIN_REDIRECT_URL_FAILURE', '/')
    form = BrowserIDForm(data=request.POST)
    if form.is_valid():
        assertion = form.cleaned_data['assertion']
        host, port = _get_host_and_port(request)
        user = auth.authenticate(assertion=assertion, host=host, port=port)
        if user is not None and user.is_active:
            auth.login(request, user)
            return HttpResponseRedirect(redirect_to)
    return HttpResponseRedirect(redirect_to_failure)
