from prometheus_client import Gauge

rating_service_backlog = Gauge(
    "server_rating_service_backlog", "Number of games remaining to be rated"
)
