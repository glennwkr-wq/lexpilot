import json
import re
import shutil
import sys
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_ROOT = PROJECT_ROOT / "document_templates" / "russian_library"
MANIFEST_PATH = TARGET_ROOT / "manifest.json"


VARIABLE_RE = re.compile(r"{{\s*([^{}]+?)\s*}}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_russian_legal_templates.py <Legal-Document-Templates-main path>")
        raise SystemExit(1)

    source_root = Path(sys.argv[1]).resolve()

    if not source_root.exists():
        print(f"Source folder not found: {source_root}")
        raise SystemExit(1)

    TARGET_ROOT.mkdir(parents=True, exist_ok=True)

    manifest = []

    for source_file in source_root.rglob("*"):
        if not source_file.is_file():
            continue

        if source_file.suffix.lower() != ".docx":
            continue

        relative_path = source_file.relative_to(source_root)
        safe_relative_path = build_safe_relative_path(relative_path)

        target_file = TARGET_ROOT / safe_relative_path
        target_file.parent.mkdir(parents=True, exist_ok=True)

        variable_map = normalize_docx_template_variables(
            source_file=source_file,
            target_file=target_file,
        )

        entry = {
            "id": make_template_id(safe_relative_path),
            "title": clean_title(source_file.stem),
            "family": detect_family(relative_path),
            "category": relative_path.parts[0] if len(relative_path.parts) >= 1 else "",
            "subcategory": relative_path.parts[1] if len(relative_path.parts) >= 3 else "",
            "source_path": str(relative_path).replace("\\", "/"),
            "template_path": str(target_file.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "variables": sorted(set(variable_map.values())),
            "variable_map": variable_map,
        }

        manifest.append(entry)

    manifest = sorted(manifest, key=lambda item: (item["family"], item["category"], item["title"]))

    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Imported templates: {len(manifest)}")
    print(f"Manifest: {MANIFEST_PATH}")


def build_safe_relative_path(relative_path: Path) -> Path:
    parts = list(relative_path.parts)
    safe_parts = [safe_filename(part) for part in parts]

    return Path(*safe_parts)


def safe_filename(value: str) -> str:
    value = value.strip()
    value = value.replace("[", "_").replace("]", "_")
    value = re.sub(r"[^\wа-яА-ЯёЁ.\- ]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    value = value.strip("_")

    return value or "template"


def make_template_id(path: Path) -> str:
    value = str(path.with_suffix("")).replace("\\", "/")
    value = value.lower()
    value = transliterate(value)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value)
    value = value.strip("_")

    return value[:180] or "template"


def clean_title(value: str) -> str:
    value = value.replace("шаблон_", "")
    value = value.replace("бланк_", "")
    value = value.replace("[С представителем]", " — с представителем")
    value = value.replace("_", " ")

    return value.strip()


def detect_family(path: Path) -> str:
    text = " ".join(path.parts).lower()

    if "претенз" in text:
        return "claim"

    if "исков" in text or "иск " in text:
        return "lawsuit"

    if "договор" in text:
        return "contract"

    if "жалоб" in text:
        return "complaint"

    if "ходатай" in text:
        return "motion"

    return "document"


def normalize_docx_template_variables(source_file: Path, target_file: Path) -> dict:
    variable_map = {}

    with zipfile.ZipFile(source_file, "r") as zin:
        with zipfile.ZipFile(target_file, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)

                if item.filename.endswith(".xml"):
                    try:
                        text = data.decode("utf-8")
                    except UnicodeDecodeError:
                        zout.writestr(item, data)
                        continue

                    text = VARIABLE_RE.sub(
                        lambda match: replace_variable(match, variable_map),
                        text,
                    )
                    zout.writestr(item, text.encode("utf-8"))
                else:
                    zout.writestr(item, data)

    return variable_map


def replace_variable(match, variable_map: dict) -> str:
    original = match.group(1).strip()
    normalized = normalize_variable_name(original)

    variable_map[original] = normalized

    return "{{ " + normalized + " }}"


def normalize_variable_name(value: str) -> str:
    value = value.strip()
    value = transliterate(value)
    value = value.lower()
    value = re.sub(r"[^a-z0-9а-яё]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"_+", "_", value)
    value = value.strip("_")

    if not value:
        value = "field"

    if value[0].isdigit():
        value = "field_" + value

    return value


def transliterate(value: str) -> str:
    mapping = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l",
        "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
        "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch",
        "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e",
        "ю": "yu", "я": "ya",
    }

    result = []

    for char in value:
        lower = char.lower()

        if lower in mapping:
            replacement = mapping[lower]

            if char.isupper():
                replacement = replacement.capitalize()

            result.append(replacement)
        else:
            result.append(char)

    return "".join(result)


if __name__ == "__main__":
    main()