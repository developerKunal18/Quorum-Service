import pytest
import app as module

@pytest.fixture(autouse=True)
def reset_service():
    module.service=module.QuorumService()
    yield

@pytest.fixture
def client():
    module.app.config["TESTING"]=True
    return module.app.test_client()

def test_health(client):
    r=client.get("/health")
    assert r.status_code==200
    assert r.get_json()["status"]=="ok"

def test_default_quorum(client):
    r=client.get("/api/quorum").get_json()
    assert r["read"]==2 and r["write"]==2

def test_write_reaches_quorum(client):
    op=client.post("/api/operations",
        json={"type":"write","key":"status","value":"online"}).get_json()
    oid=op["operation_id"]
    client.post(f"/api/operations/{oid}/ack/node-1")
    assert client.get(f"/api/operations/{oid}/decision").get_json()["quorum_reached"] is False
    client.post(f"/api/operations/{oid}/ack/node-2")
    result=client.get(f"/api/operations/{oid}/decision").get_json()
    assert result["quorum_reached"] is True
    assert result["acknowledgements"]==2

def test_duplicate_ack_is_idempotent(client):
    op=client.post("/api/operations",
        json={"type":"write","key":"x","value":1}).get_json()
    oid=op["operation_id"]
    client.post(f"/api/operations/{oid}/ack/node-1")
    client.post(f"/api/operations/{oid}/ack/node-1")
    assert client.get(f"/api/operations/{oid}/decision").get_json()["acknowledgements"]==1

def test_unhealthy_node_cannot_ack(client):
    client.patch("/api/nodes/node-1",json={"healthy":False})
    op=client.post("/api/operations",
        json={"type":"write","key":"x","value":1}).get_json()
    r=client.post(f"/api/operations/{op['operation_id']}/ack/node-1")
    assert r.status_code==400

def test_unavailable_quorum(client):
    client.patch("/api/nodes/node-1",json={"healthy":False})
    client.patch("/api/nodes/node-2",json={"healthy":False})
    op=client.post("/api/operations",
        json={"type":"write","key":"x","value":1}).get_json()
    result=client.get(f"/api/operations/{op['operation_id']}/decision").get_json()
    assert result["healthy_nodes"]==1
    assert result["available_for_quorum"] is False

def test_quorum_validation(client):
    assert client.put("/api/quorum",json={"read":4,"write":2}).status_code==400
    assert client.put("/api/quorum",json={"read":1,"write":1}).status_code==200
