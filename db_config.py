import os
from typing import Tuple


def _split_host_port(host_value: str):
    """
    Accepts host values like "127.0.0.1:3306" and splits safely.
    Returns (host, port_or_none).
    """
    if not host_value:
        return host_value, None
    if host_value.count(":") == 1:
        host, maybe_port = host_value.rsplit(":", 1)
        if maybe_port.isdigit():
            return host, int(maybe_port)
    return host_value, None


def get_db_settings() -> Tuple[str, int, str, str, str]:
    # Supports both this project's MYSQL_* and Laravel-like DB_* variables.
    raw_host = os.getenv("MYSQL_HOST") or os.getenv("DB_HOST", "localhost")
    host, port_from_host = _split_host_port(raw_host)

    raw_port = os.getenv("MYSQL_PORT") or os.getenv("DB_PORT")
    if raw_port and str(raw_port).isdigit():
        port = int(raw_port)
    elif port_from_host is not None:
        port = port_from_host
    else:
        port = 3306

    user = os.getenv("MYSQL_USER") or os.getenv("DB_USERNAME", "refbot")
    password = os.getenv("MYSQL_PASSWORD") or os.getenv("DB_PASSWORD", "")
    database = os.getenv("MYSQL_DB") or os.getenv("DB_DATABASE", "refbot_db")

    return host, port, user, password, database
