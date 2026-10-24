"""Copy DATABASES into an existing Django settings module."""
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

if os.environ.get("DB_SSL_CA"):
    DATABASES["default"]["OPTIONS"].update(
        ssl={"ca": os.environ["DB_SSL_CA"]}, ssl_mode="VERIFY_IDENTITY"
    )
