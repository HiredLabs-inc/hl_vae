"""Local development. Never used on a hosted environment.

Works with no .env and no environment variables. To override a setting, copy
.env.example to .env (gitignored) or set the variable in the shell; shell
values win over .env. Only this module reads .env (DES-003).
"""

from .base import *  # noqa: F403

# Optional, gitignored. read_env only sets variables that aren't already set.
_dotenv = BASE_DIR / ".env"
if _dotenv.is_file():
    env.read_env(_dotenv)

DEBUG = env.bool("DJANGO_DEBUG", default=True)

# Dev-only key. The "django-insecure-" prefix makes `check --deploy` flag it
# if this module is ever used somewhere it shouldn't be.
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="django-insecure-dev-only-p7+l#%wo3n^wq=y$2)3ki)dhr50x&t^lnlgwk3bm(dy*3lu7-f",
)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])

# e.g. DATABASE_URL=postgres://vae:vae@host.docker.internal:5432/vae to run
# against a local Postgres (DES-008 step 1). Defaults to SQLite.
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}
