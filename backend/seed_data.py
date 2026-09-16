import os
import sys
import sqlite3
import json
import urllib.request
import urllib.error
import mimetypes
from pathlib import Path

BASE = "http://localhost:8000/api"
WORKSPACE = Path(__file__).resolve().parent.parent
PERIODS_DIR = WORKSPACE / "dataset" / "periods"
EXTENDED_CSV = WORKSPACE / "dataset" / "soc_alerts_extended.csv"
DB_PATH = WORKSPACE / "backend" / "data" / "satsa.db"

def upload_file(file_path: Path):
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    filename = file_path.name
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        f"{BASE}/upload",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as e:
        print(f"Error uploading {filename}: HTTP {e.code} - {e.read().decode('utf-8')}")
        sys.exit(1)
    except Exception as e:
        print(f"Error uploading {filename}: {e}")
        sys.exit(1)

def main():
    # 1. Clear DB
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM alerts;")
        cur.execute("DELETE FROM assessment_runs;")
        try:
            cur.execute("DELETE FROM manual_reviews;")
        except Exception:
            pass
        conn.commit()
        conn.close()
        print("Database cleared successfully.")
    else:
        print("DB does not exist yet.")

    # 2. Upload 4 period files
    period_files = [
        "period_2025_q3.csv",
        "period_2025_q4.csv",
        "period_2026_q1.csv",
        "period_2026_q2.csv",
    ]

    for p in period_files:
        file_path = PERIODS_DIR / p
        print(f"Uploading {p}...")
        data = upload_file(file_path)
        print(f"Uploaded {p}: inserted={data.get('rows_inserted') or data.get('inserted')} run_id={data.get('run_id') or data.get('id')}")

    # 3. Upload extended CSV
    print("Uploading soc_alerts_extended.csv...")
    data = upload_file(EXTENDED_CSV)
    print(f"Uploaded soc_alerts_extended.csv: inserted={data.get('rows_inserted') or data.get('inserted')} run_id={data.get('run_id') or data.get('id')}")

    print("ALL DATASETS INGESTED SUCCESSFULLY!")

if __name__ == "__main__":
    main()

