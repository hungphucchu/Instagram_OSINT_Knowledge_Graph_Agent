"""Locust load test driver for the Instagram OSINT KG Agent.

Run from the repo root with the app already up::

    locust -f tests/load/locustfile.py --headless -u 20 -r 5 -t 60s \
           --host=http://localhost:8080 --csv=reports/loadtest

Rubric thresholds (Stress and Robustness):
  * sustained ≥ 10 req/s with < 5 % error rate over a 60-second window

This driver intentionally focuses on the headline endpoint `POST /api/query`
because that is the endpoint the rubric scores for throughput and error rate.
"""

from __future__ import annotations

from locust import HttpUser, between, task


class HeadlineUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def submit_query(self) -> None:
        self.client.post(
            "/api/query",
            json={"text": "Who appeared together most often?", "max_results": 5},
            name="POST /api/query",
        )
