from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# In development, default to eager celery execution if CELERY_ALWAYS_EAGER is true or broker unreachable
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_ALWAYS_EAGER', 'True').lower() in ('true', '1', 'yes')
CELERY_TASK_EAGER_PROPAGATES = True
