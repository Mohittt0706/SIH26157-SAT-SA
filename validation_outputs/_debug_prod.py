import sys, os, json
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
from app.analytics.execution_gap import compute_execution_gap_from_csv
from app.analytics.negative_space import compute_negative_space_from_csv

companies = [
    ('Equifax', 'dataset/external/soc_alerts_equifax.csv'),
    ('JPMorgan Chase', 'dataset/external/soc_alerts_jpmorgan_chase.csv'),
    ('MGM Resorts', 'dataset/external/soc_alerts_mgm_resorts.csv'),
    ('Microsoft', 'dataset/external/soc_alerts_microsoft.csv'),
    ('T-Mobile', 'dataset/external/soc_alerts_t-mobile.csv'),
]
prod = {}
for company, fname in companies:
    eg = compute_execution_gap_from_csv(fname)
    ns = compute_negative_space_from_csv(fname)
    eg_score = eg[company]["score"]
    ns_score = ns[company]["score"]
    prod[company] = {"eg": eg_score, "ns": ns_score}
    print(json.dumps({"company": company, "eg": eg_score, "ns": ns_score, "eg_keys": list(eg.keys())}))
print(json.dumps(prod))
