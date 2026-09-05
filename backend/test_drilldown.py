import sys
sys.path.insert(0, r'C:\Users\parma\SIH26157-SAT-SA\backend')

from app.main import app, Base, engine
from app.models import AssessmentRun
Base.metadata.create_all(bind=engine)

from fastapi.testclient import TestClient
client = TestClient(app)

# First upload data
with open('C:/Users/parma/SIH26157-SAT-SA/dataset/soc_alerts_synthetic_dataset.csv', 'rb') as f:
    client.post('/api/upload', files={'file': ('soc_alerts_synthetic_dataset.csv', f, 'text/csv')})

print('=== Testing entity endpoints ===')
print()

# Test with existing entity
resp = client.get('/api/entities/Indus%20Financial%20Services')
print(f'GET /api/entities/Indus%20Financial%20Services: {resp.status_code}')
if resp.status_code == 200:
    d = resp.json()
    print(f'  entity_name: {d["entity_name"]}')
    print(f'  risk_score: {d["risk_score"]}')
    print(f'  risk_band: {d["risk_band"]}')
    print(f'  peer_metrics: {d["peer_metrics"]}')
    print(f'  component_scores: {d["component_scores"]}')
    print(f'  findings count: {len(d["findings"])}')
else:
    print(f'Error: {resp.text[:200]}')

print()

# Test with another entity
resp = client.get('/api/entities/Delta%20Rail%20Systems')
print(f'GET /api/entities/Delta%20Rail%20Systems: {resp.status_code}')
if resp.status_code == 200:
    d = resp.json()
    print(f'  entity_name: {d["entity_name"]}')
    print(f'  risk_score: {d["risk_score"]}')
    print(f'  risk_band: {d["risk_band"]}')
    print(f'  peer_metrics: {d["peer_metrics"]}')
    print(f'  component_scores: {d["component_scores"]}')
    print(f'  findings count: {len(d["findings"])}')

print()
print('=== Testing risk-scores ===')
resp = client.get('/api/risk-scores')
print(f'GET /api/risk-scores: {resp.status_code} - {len(resp.json())} entities')

print()
print('=== Testing audit endpoints ===')
resp = client.get('/api/audit/runs')
print(f'GET /api/audit/runs: {resp.status_code} - {len(resp.json())} runs')

resp = client.get('/api/audit/runs/1')
print(f'GET /api/audit/runs/1: {resp.status_code}')
if resp.status_code == 200:
    d = resp.json()
    print(f'  Has detector_config: {bool(d.get("detector_config"))}')
    print(f'  Has results_snapshot: {bool(d.get("results_snapshot"))}')