import csv, random, hashlib
from datetime import datetime, timedelta

SEED = 26157
random.seed(SEED)

START = datetime(2026, 1, 1, 0, 0)
END   = datetime(2026, 6, 30, 23, 59)
SPAN  = int((END - START).total_seconds())

SEVERITIES = ["low", "medium", "high", "critical"]
ASSETS = ["Server", "Endpoint", "Firewall", "Database", "Network Device",
          "Cloud Workload", "IoT Device", "Identity Provider"]

# ---- genuine investigation notes: large varied pool ----
ACTIONS = [
 "Reviewed source IP {ip} against internal threat intel; no IOC match.",
 "Correlated with authentication logs for user {user}; prior successful VPN session confirmed.",
 "Isolated endpoint {asset} for forensic triage; full disk scan returned clean.",
 "Traced outbound connection to approved vendor endpoint; verified against allowlist.",
 "Cross-referenced with change management ticket CHG-{num}; scheduled maintenance window.",
 "Escalated to L2 after confirming lateral movement indicators on {asset}.",
 "Validated certificate chain; expired intermediate replaced by infrastructure team.",
 "Confirmed with asset owner that {asset} was undergoing patch deployment.",
 "Ran memory capture on {asset}; no injected process artefacts identified.",
 "Blocked source {ip} at perimeter firewall pending further investigation.",
 "Checked DNS query history; domain registered 400+ days ago, low risk profile.",
 "Reviewed EDR telemetry timeline; parent process traced to legitimate installer.",
 "Contacted user {user} via Teams; confirmed they initiated the session from Mumbai office.",
 "Matched pattern against known false-positive rule FP-{num}; tuning request raised.",
 "Verified backup job schedule; traffic volume consistent with nightly replication.",
 "Queried SIEM for related events across 24h window; no corroborating activity found.",
 "Reset credentials for {user} as precaution; no evidence of compromise.",
 "Analysed PCAP sample; payload matched benign monitoring agent heartbeat.",
 "Confirmed geolocation anomaly caused by corporate VPN egress node change.",
 "Reviewed privileged access logs; elevation was approved under ticket REQ-{num}.",
 "Sandbox detonation of attachment returned no malicious behaviour.",
 "Compared hash against VirusTotal offline signature set; no detections.",
 "Identified misconfigured scanner generating repeat alerts; owner notified.",
 "Coordinated with network team; ACL change on {asset} explains traffic shift.",
 "Documented as benign positive; rule threshold adjusted after peer review.",
]
FOLLOWUPS = [
 " Closed as benign positive.",
 " No further action required.",
 " Monitoring continued for 48 hours.",
 " Root cause documented in case notes.",
 " Handed to IR team for deeper review.",
 " Added to suppression list after approval.",
 " Ticket closed with owner sign-off.",
 "",
]
USERS = ["jsmith","apatel","rkumar","mfernandes","schen","dnair","kiyer","bshah","tgeorge","nrao"]

TEMPLATE_NOTES = ["checked, ok", "reviewed", "closed", "no issue", "n/a"]

def genuine_note():
    a = random.choice(ACTIONS).format(
        ip=f"10.{random.randint(1,60)}.{random.randint(1,250)}.{random.randint(1,250)}",
        user=random.choice(USERS),
        asset=f"HOST-{random.randint(1000,9999)}",
        num=random.randint(10000,99999))
    return a + random.choice(FOLLOWUPS)

class Profile:
    def __init__(self, name, n, sev_w, closure, esc_rate, note_mode, assets, planted=None):
        self.name=name; self.n=n; self.sev_w=sev_w; self.closure=closure
        self.esc_rate=esc_rate; self.note_mode=note_mode; self.assets=assets
        self.planted=planted

# closure: (min_sec, max_sec) for normal;  ("fast", lo, hi) for execution gap
NORMAL_CLOSURE = (7200, 21600)      # 2-6 hours
NORMAL_SEV = [52, 28, 14, 6]        # low, medium, high, critical
ALL_ASSETS = ASSETS

entities = [
 # ---------- SEEDED: execution gap, blatant ----------
 Profile("Meridian Trust Bank", 285, [40,30,20,10], ("fast",45,280), 0.06, "template", ALL_ASSETS,
         "execution_gap_severe"),
 # ---------- SEEDED: execution gap, subtle ----------
 Profile("Kaveri Power Holdings", 240, [48,29,16,7], ("mixed",0.55), 0.18, "mixed", ALL_ASSETS,
         "execution_gap_subtle"),
 # ---------- SEEDED: negative space, volume collapse ----------
 Profile("Saraswati Rail Network", 11, [70,30,0,0], NORMAL_CLOSURE, 0.55, "genuine",
         ["Server","Endpoint","Database"], "negative_space_volume"),
 # ---------- SEEDED: negative space, missing severities ----------
 Profile("Nilgiri Water Authority", 175, [66,34,0,0], NORMAL_CLOSURE, 0.42, "genuine", ALL_ASSETS,
         "negative_space_severity"),
 # ---------- SEEDED: anomaly spike, volume ----------
 Profile("Arcadia Defence Systems", 760, [45,30,17,8], NORMAL_CLOSURE, 0.47, "genuine", ALL_ASSETS,
         "anomaly_volume_spike"),
 # ---------- SEEDED: anomaly, multi-feature drift ----------
 Profile("Konkan Maritime Ltd", 190, [22,26,30,22], (26000,44000), 0.81, "genuine",
         ["Server","Identity Provider","Cloud Workload"], "anomaly_multifeature"),
 # ---------- BORDERLINE: mild execution weakness, should land mid ----------
 Profile("Deccan Health Network", 205, [50,28,15,7], ("mixed",0.22), 0.29, "mixed", ALL_ASSETS,
         "borderline_mild"),
 # ---------- BASELINE x 14 ----------
 Profile("Apex Power Grid Ltd", 198, NORMAL_SEV, NORMAL_CLOSURE, 0.44, "genuine", ALL_ASSETS),
 Profile("Bharat Telecom Networks", 214, NORMAL_SEV, NORMAL_CLOSURE, 0.41, "genuine", ALL_ASSETS),
 Profile("Cauvery Logistics Corp", 187, NORMAL_SEV, NORMAL_CLOSURE, 0.46, "genuine", ALL_ASSETS),
 Profile("Eastern Grid Utility", 221, NORMAL_SEV, NORMAL_CLOSURE, 0.39, "genuine", ALL_ASSETS),
 Profile("Godavari Chemicals", 176, NORMAL_SEV, NORMAL_CLOSURE, 0.48, "genuine", ALL_ASSETS),
 Profile("Himalayan Healthcare Network", 209, NORMAL_SEV, NORMAL_CLOSURE, 0.43, "genuine", ALL_ASSETS),
 Profile("Indus Financial Services", 193, NORMAL_SEV, NORMAL_CLOSURE, 0.45, "genuine", ALL_ASSETS),
 Profile("Jupiter Aviation Control", 202, NORMAL_SEV, NORMAL_CLOSURE, 0.40, "genuine", ALL_ASSETS),
 Profile("Krishna Port Authority", 218, NORMAL_SEV, NORMAL_CLOSURE, 0.47, "genuine", ALL_ASSETS),
 Profile("Lakshmi Insurance Group", 181, NORMAL_SEV, NORMAL_CLOSURE, 0.42, "genuine", ALL_ASSETS),
 Profile("Malabar Gas Pipelines", 206, NORMAL_SEV, NORMAL_CLOSURE, 0.44, "genuine", ALL_ASSETS),
 Profile("Narmada Steel Works", 195, NORMAL_SEV, NORMAL_CLOSURE, 0.46, "genuine", ALL_ASSETS),
 Profile("Orissa Mining Federation", 212, NORMAL_SEV, NORMAL_CLOSURE, 0.41, "genuine", ALL_ASSETS),
 Profile("Pennar Cement Industries", 189, NORMAL_SEV, NORMAL_CLOSURE, 0.45, "genuine", ALL_ASSETS),
]

rows = []
n = 0
for p in entities:
    # per-entity template pool for the 'template' mode so duplication is entity-specific
    ent_templates = random.sample(TEMPLATE_NOTES, 2)
    for i in range(p.n):
        n += 1
        created = START + timedelta(seconds=random.randint(0, SPAN))
        sev = random.choices(SEVERITIES, weights=p.sev_w)[0]

        # closure
        if isinstance(p.closure, tuple) and p.closure[0] == "fast":
            dur = random.randint(p.closure[1], p.closure[2])
        elif isinstance(p.closure, tuple) and p.closure[0] == "mixed":
            frac = p.closure[1]
            if sev in ("critical","high") and random.random() < frac:
                dur = random.randint(60, 290)
            else:
                dur = random.randint(*NORMAL_CLOSURE)
        else:
            dur = random.randint(*p.closure)

        # a few genuinely open alerts everywhere
        still_open = random.random() < 0.03
        closed = "" if still_open else (created + timedelta(seconds=dur)).strftime("%Y-%m-%d %H:%M:%S")

        # escalation
        if sev == "critical":
            esc = random.random() < min(0.95, p.esc_rate * 1.7)
        elif sev == "high":
            esc = random.random() < p.esc_rate
        else:
            esc = random.random() < p.esc_rate * 0.35

        # notes
        if p.note_mode == "template":
            note = random.choice(ent_templates)
        elif p.note_mode == "mixed":
            note = random.choice(ent_templates) if random.random() < 0.45 else genuine_note()
        else:
            note = genuine_note()
            if random.random() < 0.04:
                note = ""      # occasional blank everywhere, realistic

        rows.append([
            f"ALT{n:06d}", p.name, sev,
            created.strftime("%Y-%m-%d %H:%M:%S"), closed,
            "yes" if esc else "no", note, random.choice(p.assets)
        ])

random.shuffle(rows)

cols = ["alert_id","entity_name","severity","created_time","closed_time",
        "escalated","investigation_notes","asset_type"]
with open("soc_alerts_extended.csv","w",newline="",encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(cols); w.writerows(rows)

with open("answer_key_extended_INTERNAL_ONLY.csv","w",newline="",encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["entity_name","planted_pattern","expected_primary_detector","notes"])
    for p in entities:
        if p.planted:
            det = {"execution_gap_severe":"execution_gap",
                   "execution_gap_subtle":"execution_gap",
                   "negative_space_volume":"negative_space",
                   "negative_space_severity":"negative_space",
                   "anomaly_volume_spike":"anomaly",
                   "anomaly_multifeature":"anomaly",
                   "borderline_mild":"execution_gap"}[p.planted]
            w.writerow([p.name, p.planted, det, ""])
        else:
            w.writerow([p.name, "baseline", "-", "normal operations"])

print("rows:", len(rows), "entities:", len(entities))
