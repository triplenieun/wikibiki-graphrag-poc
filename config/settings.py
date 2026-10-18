"""Local learning settings: Neo4j is accessed through its official driver."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Existing environment variables take precedence over .env.
load_dotenv(BASE_DIR / ".env", override=False, encoding="utf-8-sig")

# Review tokens must never use a public, hard-coded signing key.
# Set a persistent key in .env when drafts must survive a server restart.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or secrets.token_urlsafe(48)
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() in {"true", "1", "yes"}
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]
INSTALLED_APPS = ["django.contrib.staticfiles", "graphlab"]
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
}]
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DATA_UPLOAD_MAX_MEMORY_SIZE = 262144
CSRF_FAILURE_VIEW = "graphlab.rag_views.csrf_failure"
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
# No relational models are used. Django auth/admin/sessions can be added later
# using a separate relational DB; Neo4j is not a Django ORM backend here.
DATABASES = {}
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Select the actual server explicitly. No fallback between providers.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "240"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "700"))
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "")
LITELLM_MODEL = os.getenv("LITELLM_MODEL", "")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "")
LITELLM_TIMEOUT = float(os.getenv("LITELLM_TIMEOUT", "120"))
LITELLM_MAX_TOKENS = int(os.getenv("LITELLM_MAX_TOKENS", "700"))
LLM_EXTRACTION_MAX_TOKENS = int(os.getenv("LLM_EXTRACTION_MAX_TOKENS", "3000"))
OLLAMA_EXTRACTION_NUM_CTX = int(os.getenv("OLLAMA_EXTRACTION_NUM_CTX", "32768"))
