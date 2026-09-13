"""Regression contracts for the release-backed workspace, not biological validation."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def trace(client, **params):
    r = client.get("/api/pathway", params=params)
    assert r.status_code == 200, r.text
    return r.json()

@pytest.mark.parametrize("species", ["male", "female"])
def test_real_snapshot(client, species):
    t = trace(client, species=species)
    assert t["parameters"]["mode"] == "release"
    assert t["provenance"]["snapshot_sha256"]
    assert 1 < len(t["nodes"]) <= 80
    assert all(n["id"].isdigit() and not n["synthetic"] for n in t["nodes"])
    assert t["paths"] and not t["search_truncated"]
    assert [p["cost"] for p in t["paths"]] == sorted(p["cost"] for p in t["paths"])
    assert client.get("/api/export", params={"query_id":t["query_id"]}).json() == t
    csv = client.get("/api/export", params={"query_id":t["query_id"], "format":"csv"})
    assert csv.status_code == 200 and "caveat" in csv.text

def test_synthetic_explicit_and_unavailable_modes(client):
    t = trace(client, mode="synthetic")
    assert t["parameters"]["source_id"] == "demo-male-S01"
    assert t["provenance"]["mode"] == "synthetic"
    assert client.get("/api/pathway?mode=live").status_code == 503
    assert client.get("/api/pathway?circuit=courtship").status_code == 503
    assert client.get("/api/pathway?source_id=demo-male-S01").status_code == 404
    assert client.get("/api/pathway?max_hops=99").status_code == 422
    assert client.get("/api/export?query_id=../../etc/passwd").status_code == 404
    assert trace(client, max_hops=1)["paths"] == []

def test_search_and_provisional_comparison(client):
    male = trace(client)
    options = client.get("/api/pathway/candidates", params={"path_id":male["query_id"]}).json()
    assert options["confidence"] == "unvalidated" and options["candidates"]
    female = trace(client, species="female", source_id=options["candidates"][0]["id"])
    params = {"male_path_id":male["query_id"],"female_path_id":female["query_id"]}
    diff = client.get("/api/pathway/diff",params=params)
    assert diff.status_code == 200
    assert "not a neuron-level homology" in diff.json()["alignment"]
    assert diff.json()["edges"]
    mismatch = trace(client, species="female", source_id=options["candidates"][0]["id"], max_hops=4)
    assert client.get("/api/pathway/diff",params={**params,"female_path_id":mismatch["query_id"]}).status_code == 422
    found = client.get("/api/neurons/search?query=DNp01&mode=release").json()["neurons"]
    assert len(found) == 2

def test_lesion_stats_and_reproducibility(client):
    t = trace(client)
    body = {"path_id":t["query_id"],"neuron_ids":[t["parameters"]["source_id"]],"controls":10,"seed":42}
    lesion = client.post("/api/knockout",json=body)
    assert lesion.status_code == 200
    assert not lesion.json()["target_reachable"]
    assert lesion.json() == client.post("/api/knockout",json=body).json()
    assert client.post("/api/knockout",json={**body,"neuron_ids":["missing"]}).status_code == 422
    stats = client.get("/api/stats/motif",params={"subgraph_id":t["query_id"]})
    assert stats.status_code == 200 and stats.json()["nodes"] == len(t["nodes"])

def test_sources_and_contracts(client):
    data = client.get("/api/sources").json()
    assert any("KOwsVDogscY" in s["url"] for s in data["sources"])
    assert any("2095553014715093022" in s["url"] for s in data["sources"])
    assert any("a-connectomics-milestone" in s["url"] for s in data["sources"])
    checks = client.get("/api/validation/contracts").json()["checks"]
    assert not any(c["status"] == "fail" for c in checks)
    assert sum(c["status"] == "pass" for c in checks) >= 6

def test_simulation_audio_and_sensitivity(client):
    r = client.get("/api/circuit/courtship/simulate")
    assert r.status_code == 200
    result = r.json()
    assert result["provenance"]["mode"] == "synthetic"
    assert not result["reference"]["validated"]
    audio = client.get(f"/api/audio/{result['query_id']}.wav")
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF"
    sweep = client.get("/api/circuit/courtship/sensitivity")
    assert sweep.status_code == 200 and sweep.json()["total_runs"] == 18

def test_production_page(client):
    from backend.app.main import DIST
    if DIST.exists():
        response = client.get("/")
        assert response.status_code == 200 and '<div id="root">' in response.text
