from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    JWT_ACCESS_TTL=(int, 30),
    JWT_REFRESH_TTL=(int, 7),
    MODEL_CONTEXT_SIZE=(int, 8192),
    MODEL_N_THREADS=(int, 4),
    CONN_MAX_AGE=(int, 60),
)

environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'rest_framework',
    'corsheaders',
    'storages',
    'users',
    'chat',
    'ai',
    'memory',
    'files',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': env.db_url('DATABASE_URL', default='sqlite:///db.sqlite3'),
}
DATABASES['default']['CONN_MAX_AGE'] = env('CONN_MAX_AGE')
DATABASES['default']['CONN_HEALTH_CHECKS'] = True

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.ScryptPasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:3000'])
CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env('JWT_ACCESS_TTL')),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=env('JWT_REFRESH_TTL')),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

MEDIA_URL = '/uploads/'
MEDIA_ROOT = str(BASE_DIR / 'uploads')

FRONTEND_ENABLED = env('FRONTEND_ENABLED', default=True)

MODEL_PATH = env('MODEL_PATH', default='')
MODEL_CONTEXT_SIZE = env('MODEL_CONTEXT_SIZE')
MODEL_N_THREADS = env('MODEL_N_THREADS')
SEARCH_PROVIDER = env('SEARCH_PROVIDER', default='duckduckgo')
TAVILY_API_KEY = env('TAVILY_API_KEY', default='')
EXA_API_KEY = env('EXA_API_KEY', default='')
BRAVE_API_KEY = env('BRAVE_API_KEY', default='')
OPENROUTER_API_KEY = env('OPENROUTER_API_KEY', default='')
OPENROUTER_BASE_URL = env('OPENROUTER_BASE_URL', default='https://openrouter.ai/api/v1')
ENABLE_SEARCH = env.bool('ENABLE_SEARCH', default=True)
ENABLE_MEMORY = env.bool('ENABLE_MEMORY', default=True)
ENABLE_VISION = env.bool('ENABLE_VISION', default=False)
ENABLE_CODE_EXECUTION = env.bool('ENABLE_CODE_EXECUTION', default=False)
ENABLE_CALCULATOR = env.bool('ENABLE_CALCULATOR', default=False)
ENABLE_OBSERVABILITY = env.bool('ENABLE_OBSERVABILITY', default=True)
ENABLE_QUERY_PLANNER = env.bool('ENABLE_QUERY_PLANNER', default=True)
MAX_PAGE_EXCERPT = env.int('MAX_PAGE_EXCERPT', default=500)
PUBLIC_BASE_URL = env('PUBLIC_BASE_URL', default='http://localhost:8000')
