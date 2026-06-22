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

def get_all_cases() -> list[dict]:
    ensure_workspace_tables()

    with SessionLocal() as session:
        rows = session.execute(text("""
            SELECT id, title, client_name, opponent_name, category, status,
                   description, next_action, deadline, created_at, updated_at
            FROM cases
            ORDER BY updated_at DESC, id DESC
        """)).mappings().fetchall()

    return [dict(row) for row in rows]


def create_case(data: dict) -> dict:
    ensure_workspace_tables()

    title = (data.get("title") or "").strip()

    if not title:
        raise ValueError("Название дела обязательно.")

    payload = {
        "title": title,
        "client_name": (data.get("client_name") or "").strip(),
        "opponent_name": (data.get("opponent_name") or "").strip(),
        "category": (data.get("category") or "").strip(),
        "status": (data.get("status") or "new").strip(),
        "description": (data.get("description") or "").strip(),
        "next_action": (data.get("next_action") or "").strip(),
        "deadline": (data.get("deadline") or "").strip() or None,
    }

    with SessionLocal() as session:
        row = session.execute(text("""
            INSERT INTO cases (
                title, client_name, opponent_name, category, status,
                description, next_action, deadline, updated_at
            )
            VALUES (
                :title, :client_name, :opponent_name, :category, :status,
                :description, :next_action, :deadline, NOW()
            )
            RETURNING id, title, client_name, opponent_name, category, status,
                      description, next_action, deadline, created_at, updated_at
        """), payload).mappings().fetchone()

        session.commit()

    return dict(row)


def update_case(case_id: int, data: dict) -> dict:
    ensure_workspace_tables()

    title = (data.get("title") or "").strip()

    if not title:
        raise ValueError("Название дела обязательно.")

    payload = {
        "id": case_id,
        "title": title,
        "client_name": (data.get("client_name") or "").strip(),
        "opponent_name": (data.get("opponent_name") or "").strip(),
        "category": (data.get("category") or "").strip(),
        "status": (data.get("status") or "new").strip(),
        "description": (data.get("description") or "").strip(),
        "next_action": (data.get("next_action") or "").strip(),
        "deadline": (data.get("deadline") or "").strip() or None,
    }

    with SessionLocal() as session:
        row = session.execute(text("""
            UPDATE cases
            SET
                title = :title,
                client_name = :client_name,
                opponent_name = :opponent_name,
                category = :category,
                status = :status,
                description = :description,
                next_action = :next_action,
                deadline = :deadline,
                updated_at = NOW()
            WHERE id = :id
            RETURNING id, title, client_name, opponent_name, category, status,
                      description, next_action, deadline, created_at, updated_at
        """), payload).mappings().fetchone()

        session.commit()

    if not row:
        raise ValueError("Дело не найдено.")

    return dict(row)


def delete_case(case_id: int) -> None:
    ensure_workspace_tables()

    with SessionLocal() as session:
        result = session.execute(
            text("DELETE FROM cases WHERE id = :id"),
            {"id": case_id},
        )
        session.commit()

    if result.rowcount == 0:
        raise ValueError("Дело не найдено.")

def get_all_tasks() -> list[dict]:
    ensure_workspace_tables()

    with SessionLocal() as session:
        rows = session.execute(text("""
            SELECT
                t.id, t.case_id, t.title, t.description, t.due_date,
                t.priority, t.status, t.created_at, t.updated_at,
                c.title AS case_title
            FROM tasks t
            LEFT JOIN cases c ON c.id = t.case_id
            ORDER BY
                CASE
                    WHEN t.status = 'done' THEN 1
                    ELSE 0
                END,
                CASE
                    WHEN t.due_date IS NULL THEN 1
                    ELSE 0
                END,
                t.due_date ASC,
                t.id DESC
        """)).mappings().fetchall()

    return [dict(row) for row in rows]


def create_task(data: dict) -> dict:
    ensure_workspace_tables()

    title = (data.get("title") or "").strip()

    if not title:
        raise ValueError("Название задачи обязательно.")

    case_id_value = data.get("case_id") or None

    payload = {
        "case_id": int(case_id_value) if case_id_value else None,
        "title": title,
        "description": (data.get("description") or "").strip(),
        "due_date": (data.get("due_date") or "").strip() or None,
        "priority": (data.get("priority") or "normal").strip(),
        "status": (data.get("status") or "open").strip(),
    }

    with SessionLocal() as session:
        row = session.execute(text("""
            INSERT INTO tasks (
                case_id, title, description, due_date, priority, status, updated_at
            )
            VALUES (
                :case_id, :title, :description, :due_date, :priority, :status, NOW()
            )
            RETURNING id, case_id, title, description, due_date,
                      priority, status, created_at, updated_at
        """), payload).mappings().fetchone()

        session.commit()

    return dict(row)


def update_task(task_id: int, data: dict) -> dict:
    ensure_workspace_tables()

    title = (data.get("title") or "").strip()

    if not title:
        raise ValueError("Название задачи обязательно.")

    case_id_value = data.get("case_id") or None

    payload = {
        "id": task_id,
        "case_id": int(case_id_value) if case_id_value else None,
        "title": title,
        "description": (data.get("description") or "").strip(),
        "due_date": (data.get("due_date") or "").strip() or None,
        "priority": (data.get("priority") or "normal").strip(),
        "status": (data.get("status") or "open").strip(),
    }

    with SessionLocal() as session:
        row = session.execute(text("""
            UPDATE tasks
            SET
                case_id = :case_id,
                title = :title,
                description = :description,
                due_date = :due_date,
                priority = :priority,
                status = :status,
                updated_at = NOW()
            WHERE id = :id
            RETURNING id, case_id, title, description, due_date,
                      priority, status, created_at, updated_at
        """), payload).mappings().fetchone()

        session.commit()

    if not row:
        raise ValueError("Задача не найдена.")

    return dict(row)


def delete_task(task_id: int) -> None:
    ensure_workspace_tables()

    with SessionLocal() as session:
        result = session.execute(
            text("DELETE FROM tasks WHERE id = :id"),
            {"id": task_id},
        )
        session.commit()

    if result.rowcount == 0:
        raise ValueError("Задача не найдена.")