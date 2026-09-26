# Quorum Service

A Flask service demonstrating quorum-based decisions in distributed systems.

## Features
- Register/remove nodes
- Mark nodes healthy or unhealthy
- Configure read/write quorum
- Create operations and record acknowledgements
- Check whether an operation reached quorum
- Thread-safe in-memory implementation
- Health and statistics endpoints
- Pytest tests

## Run
```bash
pip install -r requirements.txt
python app.py
```

## API
- `GET /health`
- `GET /api/nodes`
- `POST /api/nodes`
- `DELETE /api/nodes/<node_id>`
- `PATCH /api/nodes/<node_id>`
- `GET /api/quorum`
- `PUT /api/quorum`
- `POST /api/operations`
- `POST /api/operations/<operation_id>/ack/<node_id>`
- `GET /api/operations/<operation_id>`
- `GET /api/operations/<operation_id>/decision`
- `GET /api/stats`

## Concepts
Quorum, majority decisions, read quorum, write quorum, replica availability, fault tolerance and distributed systems.
