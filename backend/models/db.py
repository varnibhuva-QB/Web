import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta

import pyodbc

DEFAULT_SERVER = "ADMIN\\SQLEXPRESS"
DEFAULT_DATABASE = "leads_db"
DEFAULT_OPTIONS = "Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;"
PASSWORD_SALT = os.getenv('PASSWORD_SALT', 'leadgen_secret_salt')


def build_conn_str(server, database):
    return (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"{DEFAULT_OPTIONS}"
    )


def get_server_candidates(server):
    candidates = [server]
    if server and server.upper().endswith("\\SQLEXPRESS"):
        candidates.extend([
            "localhost\\SQLEXPRESS",
            "127.0.0.1\\SQLEXPRESS",
            f"{server},1433",
            f"tcp:{server}",
            "tcp:localhost\\SQLEXPRESS"
        ])
    return list(dict.fromkeys(candidates))


def get_connection(server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    last_error = None
    for candidate in get_server_candidates(server):
        try:
            return pyodbc.connect(build_conn_str(candidate, database))
        except pyodbc.Error as err:
            last_error = err

    raise pyodbc.Error(
        f"Unable to connect to SQL Server using {server} or alternates. Last error: {last_error}"
    )


def test_connection(server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    conn = get_connection(server, database)
    conn.close()
    return True


def hash_password(password):
    return hashlib.sha256((password + PASSWORD_SALT).encode('utf-8')).hexdigest()


def verify_password(password, password_hash):
    return hash_password(password) == password_hash


def derive_display_name(full_name):
    if not full_name:
        return None
    parts = [part.strip() for part in full_name.split() if part.strip()]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return " ".join(parts[:2])


def migrate_db(server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    """Ensure all expected columns exist, adding them if missing (safe to run on every startup)."""
    try:
        conn = get_connection(server, database)
        cursor = conn.cursor()
        # Add phone column to users if it doesn't exist yet
        cursor.execute("""
            IF COL_LENGTH('dbo.users', 'phone') IS NULL
                ALTER TABLE dbo.users ADD phone NVARCHAR(50) NULL;
        """)
        # Add two_step_enabled if missing
        cursor.execute("""
            IF COL_LENGTH('dbo.users', 'two_step_enabled') IS NULL
                ALTER TABLE dbo.users ADD two_step_enabled BIT NOT NULL DEFAULT 1;
        """)
        # Add login_count if missing
        cursor.execute("""
            IF COL_LENGTH('dbo.users', 'login_count') IS NULL
                ALTER TABLE dbo.users ADD login_count INT NOT NULL DEFAULT 0;
        """)
        # Add last_login_at if missing
        cursor.execute("""
            IF COL_LENGTH('dbo.users', 'last_login_at') IS NULL
                ALTER TABLE dbo.users ADD last_login_at DATETIME2 NULL;
        """)
        # Add profile onboarding columns if missing
        cursor.execute("""
            IF COL_LENGTH('dbo.users', 'full_name') IS NULL
                ALTER TABLE dbo.users ADD full_name NVARCHAR(200) NULL;
        """)
        cursor.execute("""
            IF COL_LENGTH('dbo.users', 'birthdate') IS NULL
                ALTER TABLE dbo.users ADD birthdate DATE NULL;
        """)
        cursor.execute("""
            IF COL_LENGTH('dbo.users', 'display_name') IS NULL
                ALTER TABLE dbo.users ADD display_name NVARCHAR(100) NULL;
        """)
        cursor.execute("""
            IF COL_LENGTH('dbo.users', 'profile_complete') IS NULL
                ALTER TABLE dbo.users ADD profile_complete BIT NOT NULL DEFAULT 0;
        """)
        conn.commit()
        conn.close()
        print("[DB] Migration completed successfully.")
    except Exception as exc:
        print(f"[DB] Migration warning (non-fatal): {exc}")





def get_user_by_email(email, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    if not email:
        return None
    conn = get_connection(server, database)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, email, phone, password_hash, is_superadmin, login_count, last_login_at, full_name, birthdate, display_name, profile_complete "
            "FROM users WHERE email = ?",
            (email.lower(),)
        )
    except pyodbc.Error:
        cursor.execute(
            "SELECT id, email, phone, password_hash, is_superadmin, login_count, last_login_at FROM users WHERE email = ?",
            (email.lower(),)
        )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    result = {
        'id': row[0],
        'email': row[1],
        'phone': row[2],
        'password_hash': row[3],
        'is_superadmin': bool(row[4]),
        'login_count': row[5],
        'last_login_at': row[6],
    }
    if len(row) >= 11:
        result.update({
            'full_name': row[7],
            'birthdate': row[8],
            'display_name': row[9],
            'profile_complete': bool(row[10]),
        })
    return result


def get_user_by_phone(phone, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    if not phone:
        return None
    conn = get_connection(server, database)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, email, phone, password_hash, is_superadmin, login_count, last_login_at, full_name, birthdate, display_name, profile_complete "
            "FROM users WHERE phone = ?",
            (phone,)
        )
    except pyodbc.Error:
        cursor.execute(
            "SELECT id, email, phone, password_hash, is_superadmin, login_count, last_login_at FROM users WHERE phone = ?",
            (phone,)
        )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    result = {
        'id': row[0],
        'email': row[1],
        'phone': row[2],
        'password_hash': row[3],
        'is_superadmin': bool(row[4]),
        'login_count': row[5],
        'last_login_at': row[6],
    }
    if len(row) >= 11:
        result.update({
            'full_name': row[7],
            'birthdate': row[8],
            'display_name': row[9],
            'profile_complete': bool(row[10]),
        })
    return result


def get_user_by_identifier(identifier, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    if not identifier:
        return None
    if '@' in identifier:
        return get_user_by_email(identifier, server, database)
    return get_user_by_phone(identifier, server, database)


if __name__ == "__main__":
    print("Running DB migration...")
    migrate_db()
    print("Done.")


def create_user(email=None, phone=None, password=None, server=DEFAULT_SERVER, database=DEFAULT_DATABASE, is_superadmin=False):
    if not password:
        raise ValueError('Password is required')
    if not email and not phone:
        raise ValueError('Email or phone is required')
    conn = get_connection(server, database)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (email, phone, password_hash, is_superadmin) VALUES (?, ?, ?, ?)",
        (email.lower() if email else None, phone if phone else None, hash_password(password), 1 if is_superadmin else 0)
    )
    conn.commit()
    try:
        cursor.execute(
            "SELECT id, email, phone, is_superadmin, full_name, birthdate, display_name, profile_complete FROM users WHERE id = ?",
            (cursor.lastrowid,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'email': row[1],
            'phone': row[2],
            'is_superadmin': bool(row[3]),
            'full_name': row[4],
            'birthdate': row[5],
            'display_name': row[6],
            'profile_complete': bool(row[7]),
        }
    except pyodbc.Error:
        cursor.execute(
            "SELECT id, email, phone, is_superadmin FROM users WHERE id = ?",
            (cursor.lastrowid,)
        )
        row = cursor.fetchone()
        return {
            'id': row[0],
            'email': row[1],
            'phone': row[2],
            'is_superadmin': bool(row[3]),
        } if row else None
    finally:
        conn.close()





def create_session(user_id, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=8)
    conn = get_connection(server, database)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (user_id, token, expires_at, is_active) VALUES (?, ?, ?, 1)",
        (user_id, token, expires_at)
    )
    conn.commit()
    conn.close()
    return token


def get_user_by_token(token, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    if not token:
        return None

    conn = get_connection(server, database)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT u.id, u.email, u.phone, u.is_superadmin, u.full_name, u.birthdate, u.display_name, u.profile_complete "
            "FROM users u "
            "JOIN sessions s ON s.user_id = u.id "
            "WHERE s.token = ? AND s.is_active = 1 AND s.expires_at > ?",
            (token, datetime.utcnow())
        )
    except pyodbc.Error:
        cursor.execute(
            "SELECT u.id, u.email, u.phone, u.is_superadmin "
            "FROM users u "
            "JOIN sessions s ON s.user_id = u.id "
            "WHERE s.token = ? AND s.is_active = 1 AND s.expires_at > ?",
            (token, datetime.utcnow())
        )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    result = {
        'id': row[0],
        'email': row[1],
        'phone': row[2],
        'is_superadmin': bool(row[3]),
    }
    if len(row) >= 8:
        result.update({
            'full_name': row[4],
            'birthdate': row[5],
            'display_name': row[6],
            'profile_complete': bool(row[7]),
        })
    return result


def update_user_contact(user_id, email=None, phone=None, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    if not email and not phone:
        raise ValueError('Email or phone is required')
    conn = get_connection(server, database)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET email = ?, phone = ? WHERE id = ?",
        (email.lower() if email else None, phone if phone else None, user_id)
    )
    conn.commit()
    conn.close()


def update_user_profile(user_id, email=None, phone=None, full_name=None, birthdate=None, display_name=None, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    if not email and not phone and not full_name and not birthdate and not display_name:
        raise ValueError('At least one profile field is required')

    profile_complete = None
    if full_name and not display_name:
        display_name = derive_display_name(full_name)

    if birthdate and isinstance(birthdate, str):
        try:
            birthdate = datetime.strptime(birthdate, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError('Birthdate must be in YYYY-MM-DD format')

    if (full_name or display_name) and birthdate:
        profile_complete = 1
    elif full_name or birthdate or display_name:
        profile_complete = 0

    conn = get_connection(server, database)
    cursor = conn.cursor()
    update_parts = []
    params = []
    if email is not None:
        update_parts.append('email = ?')
        params.append(email.lower() if email else None)
    if phone is not None:
        update_parts.append('phone = ?')
        params.append(phone if phone else None)
    if full_name is not None:
        update_parts.append('full_name = ?')
        params.append(full_name)
    if birthdate is not None:
        update_parts.append('birthdate = ?')
        params.append(birthdate)
    if display_name is not None:
        update_parts.append('display_name = ?')
        params.append(display_name)
    if profile_complete is not None:
        update_parts.append('profile_complete = ?')
        params.append(profile_complete)

    if not update_parts:
        conn.close()
        return

    update_sql = f"UPDATE users SET {', '.join(update_parts)} WHERE id = ?"
    params.append(user_id)
    cursor.execute(update_sql, params)
    conn.commit()
    conn.close()


def change_user_password(user_id, new_password, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    conn = get_connection(server, database)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(new_password), user_id)
    )
    conn.commit()
    conn.close()


def set_two_step_verification(user_id, enabled, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    conn = get_connection(server, database)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET two_step_enabled = ? WHERE id = ?",
        (1 if enabled else 0, user_id)
    )
    conn.commit()
    conn.close()


def update_login_stats(user_id, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    conn = get_connection(server, database)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET login_count = login_count + 1, last_login_at = ? WHERE id = ?",
        (datetime.utcnow(), user_id)
    )
    conn.commit()
    conn.close()


def log_scrape_activity(user_id, source, keyword, location, result_count, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    conn = get_connection(server, database)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scrape_activity (user_id, source, keyword, location, result_count) VALUES (?, ?, ?, ?, ?)",
        (user_id, source, keyword, location, result_count)
    )
    conn.commit()
    conn.close()


def get_admin_stats(server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    conn = get_connection(server, database)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM scrape_activity")
    scrape_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM leads")
    lead_count = cursor.fetchone()[0]
    cursor.execute(
        "SELECT TOP 20 u.email, s.source, s.keyword, s.location, s.result_count, s.created_at "
        "FROM scrape_activity s JOIN users u ON u.id = s.user_id "
        "ORDER BY s.created_at DESC"
    )
    rows = cursor.fetchall()
    conn.close()

    recent_activity = [
        {
            'user_email': row[0],
            'source': row[1],
            'keyword': row[2],
            'location': row[3],
            'result_count': row[4],
            'created_at': row[5].isoformat() if row[5] else None
        }
        for row in rows
    ]

    return {
        'user_count': user_count,
        'scrape_count': scrape_count,
        'lead_count': lead_count,
        'recent_activity': recent_activity,
    }


def save_leads(leads, source, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    conn = get_connection(server, database)
    cursor = conn.cursor()

    insert_sql = """
        INSERT INTO leads (business_name, phone, address, website, source, data)
        VALUES (?, ?, ?, ?, ?, ?)
    """

    for lead in leads:
        cursor.execute(insert_sql, (
            lead.get("business_name") or lead.get("company_name"),
            lead.get("phone"),
            lead.get("address"),
            lead.get("website"),
            source,
            json.dumps(lead)
        ))

    conn.commit()
    conn.close()


def get_leads(source=None, limit=100, server=DEFAULT_SERVER, database=DEFAULT_DATABASE):
    conn = get_connection(server, database)
    cursor = conn.cursor()

    query = "SELECT id, business_name, phone, address, website, source, data FROM leads"
    params = []

    if source:
        query += " WHERE source = ?"
        params.append(source)

    query += " ORDER BY id DESC OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    leads = []
    for row in rows:
        lead = {
            "id": row[0],
            "business_name": row[1],
            "phone": row[2],
            "address": row[3],
            "website": row[4],
            "source": row[5],
            "data": json.loads(row[6]) if row[6] else {}
        }
        leads.append(lead)

    return leads