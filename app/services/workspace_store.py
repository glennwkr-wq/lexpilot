from sqlalchemy import text

from app.db.session import SessionLocal


def ensure_workspace_tables() -> None:
    with SessionLocal() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS cases (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                client_name TEXT,
                opponent_name TEXT,
                category TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                description TEXT,
                next_action TEXT,
                deadline DATE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        session.execute(text("""
            ALTER TABLE cases
            ADD COLUMN IF NOT EXISTS next_action TEXT
        """))

        session.execute(text("""
            ALTER TABLE cases
            ADD COLUMN IF NOT EXISTS deadline DATE
        """))

        session.execute(text("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                case_id INTEGER REFERENCES cases(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_date DATE,
                priority TEXT NOT NULL DEFAULT 'normal',
                status TEXT NOT NULL DEFAULT 'open',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        session.commit()


def get_dashboard_workspace() -> dict:
    ensure_workspace_tables()

    with SessionLocal() as session:
        active_cases_count = session.execute(text("""
            SELECT COUNT(*)
            FROM cases
            WHERE status != 'closed'
        """)).scalar_one()

        open_tasks_count = session.execute(text("""
            SELECT COUNT(*)
            FROM tasks
            WHERE status != 'done'
        """)).scalar_one()

        recent_cases = session.execute(text("""
            SELECT id, title, client_name, opponent_name, category, status,
                   description, next_action, deadline
            FROM cases
            ORDER BY updated_at DESC, id DESC
            LIMIT 3
        """)).mappings().fetchall()

        urgent_tasks = session.execute(text("""
            SELECT t.id, t.title, t.description, t.due_date, t.priority,
                   t.status, c.title AS case_title
            FROM tasks t
            LEFT JOIN cases c ON c.id = t.case_id
            WHERE t.status != 'done'
            ORDER BY
                CASE
                    WHEN t.due_date IS NULL THEN 1
                    ELSE 0
                END,
                t.due_date ASC,
                t.id DESC
            LIMIT 3
        """)).mappings().fetchall()

    return {
        "active_cases_count": active_cases_count,
        "open_tasks_count": open_tasks_count,
        "recent_cases": [dict(row) for row in recent_cases],
        "urgent_tasks": [dict(row) for row in urgent_tasks],
    }