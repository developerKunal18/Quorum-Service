from copy import deepcopy
from threading import RLock
from uuid import uuid4
from flask import Flask, jsonify, request

app = Flask(__name__)
LOCK = RLock()
DEFAULT_NODES = ("node-1", "node-2", "node-3")


class QuorumService:
    def __init__(self):
        self.nodes = {n: {"healthy": True} for n in DEFAULT_NODES}
        self.read_quorum = 2
        self.write_quorum = 2
        self.operations = {}

    def add_node(self, node_id):
        if not node_id or len(node_id) > 64:
            raise ValueError("node_id must contain 1-64 characters")
        if node_id in self.nodes:
            raise ValueError("node already exists")
        self.nodes[node_id] = {"healthy": True}

    def remove_node(self, node_id):
        if node_id not in self.nodes:
            return False
        del self.nodes[node_id]
        return True

    def set_health(self, node_id, healthy):
        if node_id not in self.nodes:
            raise KeyError("node not found")
        self.nodes[node_id]["healthy"] = healthy

    def configure(self, read, write):
        if not isinstance(read, int) or not isinstance(write, int):
            raise ValueError("quorum values must be integers")
        if read < 1 or write < 1:
            raise ValueError("quorum values must be at least 1")
        if read > len(self.nodes) or write > len(self.nodes):
            raise ValueError("quorum cannot exceed node count")
        self.read_quorum, self.write_quorum = read, write

    def healthy_nodes(self):
        return sorted(n for n, info in self.nodes.items() if info["healthy"])

    def create_operation(self, op_type, key, value):
        if op_type not in {"read", "write"}:
            raise ValueError("operation type must be read or write")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("key must be a non-empty string")
        oid = uuid4().hex[:12]
        self.operations[oid] = {
            "operation_id": oid,
            "type": op_type,
            "key": key.strip(),
            "value": value,
            "acks": set(),
        }
        return self.public(self.operations[oid])

    def acknowledge(self, oid, node_id):
        if oid not in self.operations:
            raise KeyError("operation not found")
        if node_id not in self.nodes:
            raise KeyError("node not found")
        if not self.nodes[node_id]["healthy"]:
            raise ValueError("unhealthy node cannot acknowledge")
        self.operations[oid]["acks"].add(node_id)
        return self.public(self.operations[oid])

    def public(self, op):
        result = deepcopy(op)
        result["acks"] = sorted(op["acks"])
        result["ack_count"] = len(op["acks"])
        return result

    def decision(self, oid):
        if oid not in self.operations:
            raise KeyError("operation not found")
        op = self.operations[oid]
        required = self.read_quorum if op["type"] == "read" else self.write_quorum
        healthy = len(self.healthy_nodes())
        acks = len(op["acks"])
        return {
            "operation_id": oid,
            "type": op["type"],
            "required": required,
            "acknowledgements": acks,
            "quorum_reached": acks >= required,
            "healthy_nodes": healthy,
            "available_for_quorum": healthy >= required,
        }

    def stats(self):
        return {
            "nodes": len(self.nodes),
            "healthy_nodes": len(self.healthy_nodes()),
            "read_quorum": self.read_quorum,
            "write_quorum": self.write_quorum,
            "operations": len(self.operations),
        }


service = QuorumService()

@app.get("/health")
def health():
    with LOCK:
        return jsonify({"status":"ok","nodes":len(service.nodes),
                        "healthy_nodes":len(service.healthy_nodes())})

@app.get("/api/nodes")
def list_nodes():
    with LOCK:
        return jsonify({"nodes":[{"node_id":n,"healthy":i["healthy"]}
                                 for n,i in sorted(service.nodes.items())]})

@app.post("/api/nodes")
def add_node():
    body=request.get_json(silent=True) or {}
    try:
        with LOCK: service.add_node(str(body.get("node_id","")).strip())
        return jsonify({"node_id":str(body.get("node_id","")).strip(),"created":True}),201
    except ValueError as exc: return jsonify({"error":str(exc)}),400

@app.delete("/api/nodes/<node_id>")
def remove_node(node_id):
    with LOCK:
        if not service.remove_node(node_id):
            return jsonify({"error":"node not found"}),404
    return jsonify({"node_id":node_id,"removed":True})

@app.patch("/api/nodes/<node_id>")
def node_health(node_id):
    body=request.get_json(silent=True) or {}
    if not isinstance(body.get("healthy"),bool):
        return jsonify({"error":"healthy must be a boolean"}),400
    try:
        with LOCK: service.set_health(node_id,body["healthy"])
    except KeyError: return jsonify({"error":"node not found"}),404
    return jsonify({"node_id":node_id,"healthy":body["healthy"]})

@app.get("/api/quorum")
def get_quorum():
    with LOCK:
        return jsonify({"read":service.read_quorum,"write":service.write_quorum,
                        "nodes":len(service.nodes)})

@app.put("/api/quorum")
def set_quorum():
    body=request.get_json(silent=True) or {}
    if "read" not in body or "write" not in body:
        return jsonify({"error":"read and write are required"}),400
    try:
        with LOCK: service.configure(body["read"],body["write"])
    except ValueError as exc: return jsonify({"error":str(exc)}),400
    return jsonify({"read":service.read_quorum,"write":service.write_quorum})

@app.post("/api/operations")
def create_operation():
    body=request.get_json(silent=True) or {}
    if "type" not in body or "key" not in body:
        return jsonify({"error":"type and key are required"}),400
    try:
        with LOCK:
            return jsonify(service.create_operation(body["type"],body["key"],body.get("value"))),201
    except ValueError as exc: return jsonify({"error":str(exc)}),400

@app.post("/api/operations/<oid>/ack/<node_id>")
def acknowledge(oid,node_id):
    try:
        with LOCK: return jsonify(service.acknowledge(oid,node_id))
    except KeyError as exc: return jsonify({"error":str(exc).strip("'")}),404
    except ValueError as exc: return jsonify({"error":str(exc)}),400

@app.get("/api/operations/<oid>")
def get_operation(oid):
    with LOCK:
        if oid not in service.operations:
            return jsonify({"error":"operation not found"}),404
        return jsonify(service.public(service.operations[oid]))

@app.get("/api/operations/<oid>/decision")
def decision(oid):
    try:
        with LOCK: return jsonify(service.decision(oid))
    except KeyError: return jsonify({"error":"operation not found"}),404

@app.get("/api/stats")
def stats():
    with LOCK: return jsonify(service.stats())

if __name__=="__main__":
    app.run(debug=True)
