import sqlite3
from app.db import DB_PATH, init_db, now_iso

def migrate():
    init_db()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    fetched_at = now_iso()

    # scholarships -> policies (category='scholarship')
    cur.execute("SELECT * FROM scholarships;")
    rows = cur.fetchall()

    moved = 0
    for r in rows:
        policy_key = r["policy_key"] or f"scholarship::{r['name']}::{r['type']}::{r['link']}"

        cur.execute("""
            INSERT INTO policies
            (policy_key, name, category, provider, period, start_date, end_date, status, link,
             condition, benefit, source, source_id, fetched_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(policy_key)
            DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                provider = excluded.provider,
                period = excluded.period,
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                status = excluded.status,
                link = excluded.link,
                condition = excluded.condition,
                benefit = excluded.benefit,
                source = excluded.source,
                source_id = excluded.source_id,
                fetched_at = excluded.fetched_at,
                raw_json = excluded.raw_json;
        """, (
            policy_key,
            r["name"],
            "scholarship",
            r["type"],                 # provider로 매핑
            r["period"],
            r["start_date"],
            r["end_date"],
            r["status"],
            r["link"],
            r["condition"],
            r["grant"],                # benefit로 매핑
            "local-migration",         # source
            r["source_uddi"],          # source_id
            fetched_at,
            r["raw_json"],
        ))
        moved += 1

    conn.commit()
    conn.close()

    print(f"OK: migrated {moved} scholarships -> policies(category='scholarship')")

if __name__ == "__main__":
    migrate()