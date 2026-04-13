import pandas as pd

def export_csv():
    import pymysql

    conn = pymysql.connect(
        host="localhost",
        user="root",
        password="password",
        database="leads_db"
    )

    df = pd.read_sql("SELECT * FROM leads", conn)
    df.to_csv("leads.csv", index=False)

    return "leads.csv"