from sqlalchemy import text

from app.db.session import SessionLocal


def ensure_clients_table() -> None:
    with SessionLocal() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                client_type TEXT NOT NULL DEFAULT 'person',
                full_name TEXT NOT NULL,
                short_name TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                inn TEXT,
                ogrn TEXT,
                passport_details TEXT,
                representative TEXT,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        session.commit()


def get_all_clients() -> list[dict]:
    ensure_clients_table()

    with SessionLocal() as session:
        rows = session.execute(text("""
            SELECT
                id,
                client_type,
                full_name,
                short_name,
                phone,
                email,
                address,
                inn,
                ogrn,
                passport_details,
                representative,
                notes,
                created_at,
                updated_at
            FROM clients
            ORDER BY updated_at DESC, id DESC
        """)).mappings().fetchall()

    return [dict(row) for row in rows]


def create_client(data: dict) -> dict:
    ensure_clients_table()

    full_name = (data.get("full_name") or "").strip()

    if not full_name:
        raise ValueError("ФИО или наименование клиента обязательно.")

    payload = _build_client_payload(data)
    payload["full_name"] = full_name

    with SessionLocal() as session:
        row = session.execute(text("""
            INSERT INTO clients (
                client_type,
                full_name,
                short_name,
                phone,
                email,
                address,
                inn,
                ogrn,
                passport_details,
                representative,
                notes,
                updated_at
            )
            VALUES (
                :client_type,
                :full_name,
                :short_name,
                :phone,
                :email,
                :address,
                :inn,
                :ogrn,
                :passport_details,
                :representative,
                :notes,
                NOW()
            )
            RETURNING
                id,
                client_type,
                full_name,
                short_name,
                phone,
                email,
                address,
                inn,
                ogrn,
                passport_details,
                representative,
                notes,
                created_at,
                updated_at
        """), payload).mappings().fetchone()

        session.commit()

    return dict(row)


def update_client(client_id: int, data: dict) -> dict:
    ensure_clients_table()

    full_name = (data.get("full_name") or "").strip()

    if not full_name:
        raise ValueError("ФИО или наименование клиента обязательно.")

    payload = _build_client_payload(data)
    payload["id"] = client_id
    payload["full_name"] = full_name

    with SessionLocal() as session:
        row = session.execute(text("""
            UPDATE clients
            SET
                client_type = :client_type,
                full_name = :full_name,
                short_name = :short_name,
                phone = :phone,
                email = :email,
                address = :address,
                inn = :inn,
                ogrn = :ogrn,
                passport_details = :passport_details,
                representative = :representative,
                notes = :notes,
                updated_at = NOW()
            WHERE id = :id
            RETURNING
                id,
                client_type,
                full_name,
                short_name,
                phone,
                email,
                address,
                inn,
                ogrn,
                passport_details,
                representative,
                notes,
                created_at,
                updated_at
        """), payload).mappings().fetchone()

        session.commit()

    if not row:
        raise ValueError("Клиент не найден.")

    return dict(row)


def delete_client(client_id: int) -> None:
    ensure_clients_table()

    with SessionLocal() as session:
        result = session.execute(
            text("DELETE FROM clients WHERE id = :id"),
            {"id": client_id},
        )
        session.commit()

    if result.rowcount == 0:
        raise ValueError("Клиент не найден.")


def _build_client_payload(data: dict) -> dict:
    return {
        "client_type": (data.get("client_type") or "person").strip(),
        "short_name": (data.get("short_name") or "").strip(),
        "phone": (data.get("phone") or "").strip(),
        "email": (data.get("email") or "").strip(),
        "address": (data.get("address") or "").strip(),
        "inn": (data.get("inn") or "").strip(),
        "ogrn": (data.get("ogrn") or "").strip(),
        "passport_details": (data.get("passport_details") or "").strip(),
        "representative": (data.get("representative") or "").strip(),
        "notes": (data.get("notes") or "").strip(),
    }



def get_client_by_id(client_id: int | str | None) -> dict | None:
    ensure_clients_table()

    if not client_id:
        return None

    try:
        parsed_client_id = int(client_id)
    except (TypeError, ValueError):
        return None

    with SessionLocal() as session:
        row = session.execute(text("""
            SELECT
                id,
                client_type,
                full_name,
                short_name,
                phone,
                email,
                address,
                inn,
                ogrn,
                passport_details,
                representative,
                notes,
                created_at,
                updated_at
            FROM clients
            WHERE id = :id
            LIMIT 1
        """), {"id": parsed_client_id}).mappings().fetchone()

    return dict(row) if row else None


def build_client_context(client_data: dict | None) -> str:
    if not client_data:
        return ""

    client_type_label = _get_client_type_label(client_data.get("client_type"))

    lines = [
        "ДАННЫЕ ВЫБРАННОГО КЛИЕНТА:",
        f"Тип клиента: {client_type_label}",
        f"ФИО / наименование: {client_data.get('full_name') or ''}",
        f"Краткое имя: {client_data.get('short_name') or ''}",
        f"Телефон: {client_data.get('phone') or ''}",
        f"Email: {client_data.get('email') or ''}",
        f"Адрес: {client_data.get('address') or ''}",
        f"ИНН: {client_data.get('inn') or ''}",
        f"ОГРН / ОГРНИП: {client_data.get('ogrn') or ''}",
        f"Паспортные данные / сведения о документе: {client_data.get('passport_details') or ''}",
        f"Представитель: {client_data.get('representative') or ''}",
        f"Комментарий юриста: {client_data.get('notes') or ''}",
    ]

    return "\n".join(lines).strip()


def _get_client_type_label(client_type: str | None) -> str:
    if client_type == "person":
        return "Физическое лицо"

    if client_type == "individual_entrepreneur":
        return "Индивидуальный предприниматель"

    if client_type == "company":
        return "Организация"

    return client_type or "Не указан"