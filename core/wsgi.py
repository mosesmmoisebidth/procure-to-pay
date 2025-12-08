"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Simple boot log for pipeline verification.
print('Smart P2P Django server is starting via WSGI...')
print("Adding aother print statement here")
print("testing the github action")
application = get_wsgi_application()
