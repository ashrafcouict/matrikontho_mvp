import sqlite3, json, uuid, csv, io
from datetime import datetime, timezone
DB="matrikontho.sqlite3"
def connect(): return sqlite3.connect(DB)
def init_db():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS assessments(
        id TEXT PRIMARY KEY, timestamp TEXT, pregnancy_status TEXT, gestational_age_weeks INTEGER,
        transcript_summary TEXT, symptoms TEXT, risk_level TEXT, triggered_rules TEXT, advice TEXT,
        referral_status TEXT)""")
def save_assessment(ext,res,advice):
    aid="MK-"+uuid.uuid4().hex[:8].upper()
    with connect() as c:
        c.execute("INSERT INTO assessments VALUES(?,?,?,?,?,?,?,?,?,?)",
        (aid,datetime.now(timezone.utc).isoformat(),ext.get("pregnancy_status","unknown"),
         ext.get("gestational_age_weeks"),(ext.get("source_transcript","")[:240]),
         json.dumps(ext.get("symptoms",[]),ensure_ascii=False),res["risk_level"],
         json.dumps(res.get("rule_ids",[])),advice,"draft_only" if res["risk_level"]=="HIGH" else "not_required"))
    return aid
def list_assessments():
    with connect() as c:
        rows=c.execute("SELECT id,timestamp,pregnancy_status,gestational_age_weeks,risk_level,referral_status FROM assessments ORDER BY timestamp DESC").fetchall()
    cols=["assessment_id","timestamp","pregnancy_status","gestational_age_weeks","risk_level","referral_status"]
    return [dict(zip(cols,r)) for r in rows]
def get_assessment(aid):
    with connect() as c:
        row=c.execute("SELECT * FROM assessments WHERE id=?",(aid,)).fetchone()
    return row
def export_csv():
    rows=list_assessments(); out=io.StringIO()
    if rows:
        writer=csv.DictWriter(out,fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    return out.getvalue()
