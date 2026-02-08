import sqlite3, json

DB = 'leads.db'
conn = sqlite3.connect(DB)
c = conn.cursor()

print('Inspecting', DB)
try:
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in c.fetchall()]
    print('TABLES:', tables)
except Exception as e:
    print('Error listing tables:', e)

if 'leads' in tables:
    try:
        c.execute('SELECT COUNT(*) FROM leads')
        print('LEADS COUNT:', c.fetchone()[0])
        c.execute('SELECT id, company, score, status, created_at FROM leads ORDER BY created_at DESC LIMIT 10')
        print('LEADS SAMPLE:')
        for r in c.fetchall():
            print(' ', r)
    except Exception as e:
        print('LEADS query error:', e)

if 'sales_officers' in tables:
    try:
        c.execute('SELECT COUNT(*) FROM sales_officers')
        print('OFFICERS COUNT:', c.fetchone()[0])
        c.execute('SELECT id, name, phone, region FROM sales_officers')
        print('OFFICERS:')
        for r in c.fetchall():
            print(' ', r)
    except Exception as e:
        print('OFFICERS query error:', e)

conn.close()
