try:
    import json
except ImportError:
    import simplejson as json

import base64
import hashlib
import logging
import urllib

import httplib2

from django.conf import settings
from django.contrib.auth.models import User

log = logging.getLogger(__name__)

DEFAULT_HTTP_PORT = '80'
DEFAULT_HTTP_TIMEOUT = 5
DEFAULT_VERIFICATION_URL = 'https://browserid.org/verify'
OKAY_RESPONSE = 'okay'


def default_username_algo(email):
    # store the username as a base64 encoded sha1 of the email address
    # this protects against data leakage because usernames are often
    # treated as public identifiers (so we can't use the email address).
    username = base64.urlsafe_b64encode(
        hashlib.sha1(email).digest()).rstrip('=')
    return username


class BrowserIDBackend(object):
    supports_anonymous_user = False
    supports_object_permissions = False

    def get_audience(self, host, port):
        if port and port != DEFAULT_HTTP_PORT:
            return u'%s:%s' % (host, port)
        return host

    def _verify_http_request(self, url, qs):
        timeout = getattr(settings, 'BROWSERID_HTTP_TIMEOUT',
                          DEFAULT_HTTP_TIMEOUT)
        ca_certs = getattr(settings, 'BROWSERID_CACERT_FILE', None)
        client = httplib2.Http(timeout=timeout, ca_certs=ca_certs)
        resp, content = client.request('%s?%s' % (url, qs), 'POST')
        return json.loads(content)

    def verify(self, assertion, audience):
        """Verify assertion using an external verification service."""
        verify_url = getattr(settings, 'BROWSERID_VERIFICATION_URL',
                             DEFAULT_VERIFICATION_URL)
        result = self._verify_http_request(verify_url, urllib.urlencode({
            'assertion': assertion,
            'audience': audience
        }))
        if result['status'] == OKAY_RESPONSE:
            return result
        return False

    def authenticate(self, assertion=None, host=None, port=None):
        result = self.verify(assertion, self.get_audience(host, port))
        if result is None:
            return None
        email = result['email']
        # in the rare case that two user accounts have the same email address,
        # log and bail. randomly selecting one seems really wrong.
        users = User.objects.filter(email=email)
        if len(users) > 1:
            log.warn('%d users with email address %s.' % (len(users), email))
            return None
        if len(users) == 1:
            return users[0]
        create_user = getattr(settings, 'BROWSERID_CREATE_USER', False)
        if not create_user:
            return None
        username_algo = getattr(settings, 'BROWSERID_USERNAME_ALGO',
                                default_username_algo)
        user = User.objects.create_user(username_algo(email), email)
        user.is_active = True
        user.save()
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
