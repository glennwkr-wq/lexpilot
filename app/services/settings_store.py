from sqlalchemy import text

from app.db.session import SessionLocal


DEFAULT_PROFILE = {
    "full_name": "",
    "professional_status": "",
    "address": "",
    "phone": "",
    "email": "",
    "inn": "",
    "ogrn": "",
    "signature": "",
}


def ensure_settings_table() -> None:
    with SessionLocal() as session:
        session.execute(
            text("""
                CREATE TABLE IF NOT EXISTS lawyer_profile (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    full_name TEXT,
                    professional_status TEXT,
                    address TEXT,
                    phone TEXT,
                    email TEXT,
                    inn TEXT,
                    ogrn TEXT,
                    signature TEXT,
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
        )

        session.execute(
            text("""
                INSERT INTO lawyer_profile (id)
                VALUES (1)
                ON CONFLICT (id) DO NOTHING
            """)
        )

        session.commit()


def get_lawyer_profile() -> dict:
    ensure_settings_table()

    with SessionLocal() as session:
        row = session.execute(
            text("""
                SELECT full_name, professional_status, address, phone,
                       email, inn, ogrn, signature
                FROM lawyer_profile
                WHERE id = 1
            """)
        ).mappings().fetchone()

    if not row:
        return DEFAULT_PROFILE.copy()

    return {key: row.get(key) or "" for key in DEFAULT_PROFILE}


def save_lawyer_profile(data: dict) -> dict:
    ensure_settings_table()

    profile = {
        key: (data.get(key) or "").strip()
        for key in DEFAULT_PROFILE
    }

    with SessionLocal() as session:
        session.execute(
            text("""
                UPDATE lawyer_profile
                SET
                    full_name = :full_name,
                    professional_status = :professional_status,
                    address = :address,
                    phone = :phone,
                    email = :email,
                    inn = :inn,
                    ogrn = :ogrn,
                    signature = :signature,
                    updated_at = NOW()
                WHERE id = 1
            """),
            profile,
        )
        session.commit()

    return profile