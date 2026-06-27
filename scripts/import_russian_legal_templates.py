import html
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_ROOT = PROJECT_ROOT / "document_templates" / "russian_library"
MANIFEST_PATH = TARGET_ROOT / "manifest.json"

VARIABLE_RE = re.compile(r"{{\s*(.*?)\s*}}", re.DOTALL)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_russian_legal_templates.py <templates path>")
        raise SystemExit(1)

    source_root = Path(sys.argv[1]).resolve()

    if not source_root.exists():
        print(f"Source folder not found: {source_root}")
        raise SystemExit(1)

    if TARGET_ROOT.exists():
        shutil.rmtree(TARGET_ROOT)

    TARGET_ROOT.mkdir(parents=True, exist_ok=True)

    manifest = []

    for source_file in source_root.rglob("*"):
        if not source_file.is_file():
            continue

        if source_file.suffix.lower() != ".docx":
            continue

        relative_path = source_file.relative_to(source_root)
        readable_relative_path = repair_path(relative_path)
        safe_relative_path = build_safe_relative_path(readable_relative_path)

        target_file = TARGET_ROOT / safe_relative_path
        target_file.parent.mkdir(parents=True, exist_ok=True)

        variable_map = normalize_docx_template_variables(
            source_file=source_file,
            target_file=target_file,
        )

        clean_variables = sorted({
            value
            for value in variable_map.values()
            if is_valid_variable_name(value)
        })

        if not clean_variables:
            continue

        entry = {
            "id": make_template_id(safe_relative_path),
            "title": clean_title(readable_relative_path.stem),
            "family": detect_family(readable_relative_path),
            "category": readable_relative_path.parts[0] if len(readable_relative_path.parts) >= 1 else "",
            "subcategory": readable_relative_path.parts[1] if len(readable_relative_path.parts) >= 3 else "",
            "source_path": str(readable_relative_path).replace("\\", "/"),
            "template_path": str(target_file.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "variables": clean_variables,
            "variable_map": {
                key: value
                for key, value in variable_map.items()
                if is_valid_variable_name(value)
            },
        }

        manifest.append(entry)

    manifest = sorted(manifest, key=lambda item: (item["family"], item["category"], item["title"]))

    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Imported templates: {len(manifest)}")
    print(f"Manifest: {MANIFEST_PATH}")


def repair_path(path: Path) -> Path:
    return Path(*[repair_mojibake(part) for part in path.parts])


def repair_mojibake(value: str) -> str:
    if not isinstance(value, str):
        return value

    if "Р" not in value and "С" not in value:
        return value

    for encoding in ["cp1251", "latin1"]:
        try:
            fixed = value.encode(encoding).decode("utf-8")
        except Exception:
            continue

        if count_cyrillic(fixed) > count_cyrillic(value):
            return fixed

    return value


def count_cyrillic(value: str) -> int:
    return len(re.findall(r"[а-яА-ЯёЁ]", value or ""))


def build_safe_relative_path(relative_path: Path) -> Path:
    return Path(*[safe_filename(part) for part in relative_path.parts])


def safe_filename(value: str) -> str:
    value = repair_mojibake(value)
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
    value = repair_mojibake(value)
    value = value.replace("шаблон_", "")
    value = value.replace("бланк_", "")
    value = value.replace("[С представителем]", " — с представителем")
    value = value.replace("_", " ")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def detect_family(path: Path) -> str:
    text = " ".join(path.parts).lower()

    if "ходатай" in text:
        return "motion"

    if "претенз" in text:
        return "claim"

    if "жалоб" in text:
        return "complaint"

    if "исков" in text or "иск " in text or "иск_" in text:
        return "lawsuit"

    if "договор" in text:
        return "contract"

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

                    text = remove_word_proof_tags(text)
                    text = VARIABLE_RE.sub(
                        lambda match: replace_variable(match, variable_map),
                        text,
                    )
                    zout.writestr(item, text.encode("utf-8"))
                else:
                    zout.writestr(item, data)

    return variable_map


def remove_word_proof_tags(text: str) -> str:
    text = re.sub(r"<w:proofErr\b[^>]*/>", "", text)
    text = re.sub(r"<w:proofErr\b[^>]*>.*?</w:proofErr>", "", text, flags=re.DOTALL)
    return text


def replace_variable(match, variable_map: dict) -> str:
    raw_original = match.group(1)
    original = clean_variable_text(raw_original)
    normalized = normalize_variable_name(original)

    if not is_valid_variable_name(normalized):
        return ""

    variable_map[original] = normalized

    return "{{ " + normalized + " }}"


def clean_variable_text(value: str) -> str:
    value = value or ""
    value = html.unescape(value)

    text_parts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", value, flags=re.DOTALL)

    if text_parts:
        value = "".join(text_parts)
    else:
        value = re.sub(r"<[^>]+>", "", value)

    value = html.unescape(value)
    value = value.replace("\u00a0", " ")
    value = value.strip()

    return value


def normalize_variable_name(value: str) -> str:
    value = clean_variable_text(value)
    value = repair_mojibake(value)
    value = transliterate(value)
    value = value.lower()
    value = re.sub(r"[^a-z0-9а-яё]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"_+", "_", value)
    value = value.strip("_")

    if not value:
        return ""

    if value[0].isdigit():
        value = "field_" + value

    return value[:80]


def is_valid_variable_name(value: str) -> bool:
    value = (value or "").strip().lower()

    if not value:
        return False

    bad_markers = [
        "w_t",
        "w_r",
        "prooferr",
        "rsidr",
        "rpr",
        "rfonts",
        "times_new_roman",
        "xml_space",
        "szcs",
        "lang_w_val",
        "spellstart",
        "spellend",
        "gramend",
    ]

    if any(marker in value for marker in bad_markers):
        return False

    if len(value) > 80:
        return False

    return bool(re.match(r"^[a-zа-яё_][a-z0-9а-яё_]*$", value, flags=re.UNICODE))


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