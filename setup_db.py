import os
import hashlib
import pyodbc

SERVER = "ADMIN\\SQLEXPRESS"
DATABASE = "leads_db"
PASSWORD_SALT = os.getenv('PASSWORD_SALT', 'leadgen_secret_salt')
SUPERADMIN_EMAIL = os.getenv('SUPERADMIN_EMAIL', 'superadmin@gmail.com')
SUPERADMIN_PASSWORD = os.getenv('SUPERADMIN_PASSWORD', 'Varni@2307')

CONN_STR_MASTER = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SERVER};"
    "DATABASE=master;"
    "Trusted_Connection=yes;"
    "Encrypt=no;"
    "TrustServerCertificate=yes;"
)
CONN_STR_DB = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    "Trusted_Connection=yes;"
    "Encrypt=no;"
    "TrustServerCertificate=yes;"
)


def run_sql(cursor, sql):
    for statement in sql.strip().split("\n\n"):
        if statement.strip():
            cursor.execute(statement)


def hash_password(password):
    return hashlib.sha256((password + PASSWORD_SALT).encode('utf-8')).hexdigest()


if __name__ == "__main__":
    conn = pyodbc.connect(CONN_STR_MASTER)
    conn.autocommit = True
    cursor = conn.cursor()

    print("Ensuring database exists...")
    cursor.execute("IF DB_ID('leads_db') IS NULL CREATE DATABASE leads_db")
    cursor.close()
    conn.close()

    conn = pyodbc.connect(CONN_STR_DB)
    conn.autocommit = True
    cursor = conn.cursor()

    print("Dropping old trigger and tables if they exist...")
    cursor.execute("IF OBJECT_ID('dbo.tr_leads_insert_no_duplicate', 'TR') IS NOT NULL DROP TRIGGER dbo.tr_leads_insert_no_duplicate")
    cursor.execute("IF OBJECT_ID('dbo.duplicate_leads', 'U') IS NOT NULL DROP TABLE dbo.duplicate_leads")
    cursor.execute("IF OBJECT_ID('dbo.leads', 'U') IS NOT NULL DROP TABLE dbo.leads")

    print("Creating leads table...")
    cursor.execute("""
    CREATE TABLE dbo.leads (
        id INT IDENTITY(1,1) PRIMARY KEY,
        business_name NVARCHAR(255) NULL,
        phone NVARCHAR(100) NULL,
        address NVARCHAR(MAX) NULL,
        website NVARCHAR(MAX) NULL,
        source NVARCHAR(100) NULL,
        data NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        _dedup_hash AS HASHBYTES('SHA2_256',
            COALESCE(business_name, '') + '||' +
            COALESCE(phone, '') + '||' +
            COALESCE(address, '') + '||' +
            COALESCE(website, '') + '||' +
            COALESCE(source, '')
        ) PERSISTED
    )
    """)

    print("Creating duplicate_leads table...")
    cursor.execute("""
    CREATE TABLE dbo.duplicate_leads (
        id INT IDENTITY(1,1) PRIMARY KEY,
        business_name NVARCHAR(255) NULL,
        phone NVARCHAR(100) NULL,
        address NVARCHAR(MAX) NULL,
        website NVARCHAR(MAX) NULL,
        source NVARCHAR(100) NULL,
        data NVARCHAR(MAX) NULL,
        duplicate_of_id INT NULL,
        duplicate_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    )
    """)

    print("Creating dedup index on leads...")
    cursor.execute("""
    CREATE UNIQUE INDEX UX_Leads_UniqueKey
    ON dbo.leads (_dedup_hash)
    """)

    print("Creating user and auth tables...")
    cursor.execute("""
    CREATE TABLE dbo.users (
        id INT IDENTITY(1,1) PRIMARY KEY,
        email NVARCHAR(255) NULL,
        phone NVARCHAR(50) NULL,
        password_hash NVARCHAR(255) NOT NULL,
        is_superadmin BIT NOT NULL DEFAULT 0,
        two_step_enabled BIT NOT NULL DEFAULT 1,
        phone_verified BIT NOT NULL DEFAULT 0,
        login_count INT NOT NULL DEFAULT 0,
        last_login_at DATETIME2 NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT CK_Users_EmailOrPhone CHECK (email IS NOT NULL OR phone IS NOT NULL)
    )
    """)

    cursor.execute("""
    CREATE UNIQUE INDEX UX_Users_Email ON dbo.users(email) WHERE email IS NOT NULL;
    """)

    cursor.execute("""
    CREATE UNIQUE INDEX UX_Users_Phone ON dbo.users(phone) WHERE phone IS NOT NULL;
    """)

    cursor.execute("""
    CREATE TABLE dbo.otp_codes (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        code NVARCHAR(10) NOT NULL,
        expires_at DATETIME2 NOT NULL,
        used BIT NOT NULL DEFAULT 0,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE dbo.sessions (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        token NVARCHAR(255) NOT NULL,
        expires_at DATETIME2 NOT NULL,
        is_active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE dbo.scrape_activity (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        source NVARCHAR(100) NULL,
        keyword NVARCHAR(255) NULL,
        location NVARCHAR(255) NULL,
        result_count INT NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    )
    """)

    print("Creating default superadmin user...")
    cursor.execute("""
    INSERT INTO dbo.users (email, password_hash, is_superadmin)
    VALUES (?, ?, 1)
    """, (SUPERADMIN_EMAIL.lower(), hash_password(SUPERADMIN_PASSWORD)))

    print("Creating duplicate-handling trigger...")
    cursor.execute("""
    CREATE TRIGGER dbo.tr_leads_insert_no_duplicate
    ON dbo.leads
    INSTEAD OF INSERT
    AS
    BEGIN
        SET NOCOUNT ON;

        INSERT INTO dbo.leads (business_name, phone, address, website, source, data)
        SELECT i.business_name, i.phone, i.address, i.website, i.source, i.data
        FROM inserted i
        WHERE NOT EXISTS (
            SELECT 1 FROM dbo.leads l
            WHERE COALESCE(l.business_name, '') = COALESCE(i.business_name, '')
              AND COALESCE(l.phone, '') = COALESCE(i.phone, '')
              AND COALESCE(l.address, '') = COALESCE(i.address, '')
              AND COALESCE(l.website, '') = COALESCE(i.website, '')
              AND COALESCE(l.source, '') = COALESCE(i.source, '')
        );

        INSERT INTO dbo.duplicate_leads (business_name, phone, address, website, source, data, duplicate_of_id)
        SELECT i.business_name, i.phone, i.address, i.website, i.source, i.data, l.id
        FROM inserted i
        CROSS APPLY (
            SELECT TOP 1 id FROM dbo.leads l
            WHERE COALESCE(l.business_name, '') = COALESCE(i.business_name, '')
              AND COALESCE(l.phone, '') = COALESCE(i.phone, '')
              AND COALESCE(l.address, '') = COALESCE(i.address, '')
              AND COALESCE(l.website, '') = COALESCE(i.website, '')
              AND COALESCE(l.source, '') = COALESCE(i.source, '')
        ) AS l
        WHERE EXISTS (
            SELECT 1 FROM dbo.leads l2
            WHERE COALESCE(l2.business_name, '') = COALESCE(i.business_name, '')
              AND COALESCE(l2.phone, '') = COALESCE(i.phone, '')
              AND COALESCE(l2.address, '') = COALESCE(i.address, '')
              AND COALESCE(l2.website, '') = COALESCE(i.website, '')
              AND COALESCE(l2.source, '') = COALESCE(i.source, '')
        );
    END
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print("Database structure created successfully.")

