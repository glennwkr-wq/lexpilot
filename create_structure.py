from pathlib import Path

folders = [
    "app",
    "app/core",
    "app/db",
    "app/models",
    "app/providers",
    "app/providers/llm",
    "app/services",
    "app/services/ai",
    "app/services/documents",
    "app/services/cases",
    "app/services/timeline",
    "app/web",
    "app/web/routes",
    "app/web/static",
    "app/web/static/css",
    "app/web/static/js",
    "app/web/templates",
    "knowledge_base",
    "prompts",
    "uploads",
    "generated",
]

files = [
    ".env",
    "requirements.txt",
    "main.py",

    "app/__init__.py",

    "app/core/__init__.py",
    "app/core/config.py",

    "app/db/__init__.py",
    "app/db/base.py",
    "app/db/session.py",

    "app/models/__init__.py",

    "app/providers/__init__.py",
    "app/providers/llm/__init__.py",
    "app/providers/llm/openai.py",

    "app/web/__init__.py",
    "app/web/app.py",

    "app/web/routes/__init__.py",
    "app/web/routes/dashboard.py",

    "app/web/templates/base.html",
    "app/web/templates/dashboard.html",

    "app/web/static/css/style.css",
]

for folder in folders:
    Path(folder).mkdir(parents=True, exist_ok=True)

for file in files:
    path = Path(file)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        path.touch()

print("===================================")
print("LexPilot structure created")
print("===================================")

for folder in folders:
    print(f"[DIR ] {folder}")

for file in files:
    print(f"[FILE] {file}")