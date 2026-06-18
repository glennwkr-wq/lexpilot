from pathlib import Path

# 1. Procfile для Render
Path("Procfile").write_text(
    "web: gunicorn main:app\n",
    encoding="utf-8"
)

# 2. .gitignore — чтобы не залить секреты и мусор в GitHub
Path(".gitignore").write_text(
    """venv/
__pycache__/
*.pyc
.env
uploads/
generated/
.DS_Store
.idea/
.vscode/
""",
    encoding="utf-8"
)

# 3. runtime.txt — версия Python для Render
Path("runtime.txt").write_text(
    "python-3.12.5\n",
    encoding="utf-8"
)

# 4. requirements.txt — добавляем зависимости, если их нет
req_path = Path("requirements.txt")

if req_path.exists():
    lines = req_path.read_text(encoding="utf-8").splitlines()
else:
    lines = []

needed = [
    "flask",
    "python-dotenv",
    "sqlalchemy",
    "openai",
    "python-docx",
    "pypdf",
    "docx2txt",
    "bcrypt",
    "PyJWT",
    "gunicorn",
    "psycopg[binary]",
]

existing = {line.strip().lower() for line in lines if line.strip()}

for package in needed:
    if package.lower() not in existing:
        lines.append(package)

req_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("Render files created:")
print("- Procfile")
print("- .gitignore")
print("- runtime.txt")
print("- requirements.txt updated")