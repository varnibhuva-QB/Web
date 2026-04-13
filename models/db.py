import pymysql
import json

def save_leads(leads, source):
    conn = pymysql.connect(
        host="localhost",
        user="root",
        password="password",
        database="leads_db"
    )

    cursor = conn.cursor()

    for lead in leads:
        cursor.execute("""
            INSERT INTO leads (business_name, phone, address, source, data)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            lead.get("business_name") or lead.get("company_name"),
            lead.get("phone"),
            lead.get("address"),
            source,
            json.dumps(lead)
        ))

    conn.commit()
    conn.close()

def get_leads(source=None, limit=100):
    conn = pymysql.connect(
        host="localhost",
        user="root",
        password="password",
        database="leads_db"
    )

    cursor = conn.cursor()
    query = "SELECT * FROM leads"
    params = []
    if source:
        query += " WHERE source = %s"
        params.append(source)
    query += " ORDER BY id DESC LIMIT %s"
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
            "source": row[4],
            "data": json.loads(row[5]) if row[5] else {}
        }
        leads.append(lead)

    return leads