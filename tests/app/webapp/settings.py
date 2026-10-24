import os
from pathlib import Path
SECRET_KEY = "isolated-ci-project-no-real-users"
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
INSTALLED_APPS = ["probe"]
MIDDLEWARE = []
ROOT_URLCONF = "webapp.urls"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
USE_TZ = True
TIME_ZONE = "UTC"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql",
    "NAME": os.environ["DB_NAME"],
    "USER": os.environ["DB_USER"],
    "PASSWORD": os.environ["DB_PASSWORD"],
    "HOST": "127.0.0.1",
    "PORT": int(os.environ["DB_PORT"]),
    "CONN_MAX_AGE": int(os.environ.get("CONN_MAX_AGE", "0")),
    "OPTIONS": {
        "charset": "utf8mb4",
        "ssl": {"ca": str(Path(os.environ.get("CERTS_DIR", "/certs")) / "ca.pem")},
        "ssl_mode": "VERIFY_IDENTITY",
        "connect_timeout": 10,
        "read_timeout": 20,
        "write_timeout": 20,
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
    },
}}
