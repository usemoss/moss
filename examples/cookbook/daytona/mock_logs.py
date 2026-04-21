"""
Mock log generator — runs inside a Daytona sandbox via code_run to test our QA Agent.

Produces 1 200 structured log entries across 6 services, covering common
production events: auth failures, DB timeouts, memory pressure, job failures,
cache evictions, and scheduled task errors.
"""

import random
from datetime import datetime, timedelta

random.seed(42)

SERVICES = ["auth-service", "api-gateway", "db-proxy", "worker", "scheduler", "cache"]

EVENTS = {
    "auth-service": [
        ("INFO",  "User login successful for alice@example.com"),
        ("ERROR", "Authentication failed: invalid password for admin@example.com"),
        ("WARN",  "JWT token expires in 5 minutes for session abc123"),
        ("ERROR", "Rate limit exceeded: 200 req/min from 10.0.0.42"),
        ("INFO",  "New user registered: bob@example.com"),
        ("ERROR", "Session not found for token xyz789"),
        ("INFO",  "Password reset email sent to charlie@example.com"),
    ],
    "api-gateway": [
        ("INFO",  "GET /api/v1/users 200 38ms"),
        ("INFO",  "POST /api/v1/orders 201 120ms"),
        ("ERROR", "GET /api/v1/products 500 Internal Server Error"),
        ("WARN",  "PUT /api/v1/users/99 404 User not found"),
        ("ERROR", "POST /api/v1/payments 503 db-proxy timeout after 30s"),
        ("INFO",  "GET /api/v1/health 200 1ms"),
        ("WARN",  "Slow response: DELETE /api/v1/sessions 890ms"),
    ],
    "db-proxy": [
        ("ERROR", "Connection pool exhausted: 50/50 active connections"),
        ("WARN",  "Slow query (3.2s): SELECT * FROM orders WHERE status='pending'"),
        ("INFO",  "Database connection established to postgres:5432"),
        ("ERROR", "Query timeout after 30s on table: orders"),
        ("WARN",  "Replica lag is 8s — reads routed back to primary"),
        ("ERROR", "Deadlock detected between transactions T1 and T2"),
        ("INFO",  "Index rebuild completed on orders.created_at (12s)"),
    ],
    "worker": [
        ("WARN",  "Job queue depth: 1450 pending"),
        ("ERROR", "Task failed after 3 retries: job_id=789 send_email"),
        ("WARN",  "Memory usage: 89% (7.1 GB / 8 GB)"),
        ("ERROR", "CPU spike: 97% sustained for 90s — throttling workers"),
        ("INFO",  "Job completed: image_resize duration=1.8s"),
        ("ERROR", "OOM killer invoked — worker pid=4321 terminated"),
        ("WARN",  "Dead-letter queue: 12 jobs moved after repeated failures"),
    ],
    "scheduler": [
        ("INFO",  "Cron started: nightly-backup 02:00"),
        ("INFO",  "Cron completed: nightly-backup duration=43m"),
        ("ERROR", "Scheduled task failed: cleanup-temp-files — disk full (98%)"),
        ("WARN",  "Job delayed: dependency check not met for report-generation"),
        ("INFO",  "Next run: report-generation scheduled at 06:00"),
    ],
    "cache": [
        ("INFO",  "Cache hit rate: 91.4% (last 5 min)"),
        ("WARN",  "Evicting 2000 expired keys (memory pressure)"),
        ("ERROR", "Redis connection timeout 150ms — falling back to DB"),
        ("INFO",  "Cache invalidated for pattern: product:*"),
        ("WARN",  "Memory usage: 920 MB / 1 GB (92%)"),
    ],
}

base_time = datetime(2025, 4, 15, 0, 0, 0)
entries = []
for _ in range(1200):
    service = random.choice(SERVICES)
    level, message = random.choice(EVENTS[service])
    offset_s = random.uniform(0, 86400)
    ts = (base_time + timedelta(seconds=offset_s)).strftime("%Y-%m-%dT%H:%M:%S")
    entries.append((ts, level, service, message))

entries.sort(key=lambda x: x[0])
for ts, level, service, message in entries:
    print(f"{ts} {level} {service}: {message}")
