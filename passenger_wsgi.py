"""Ponto de entrada para hospedagem cPanel/Passenger (HostGator: "Setup Python App").

No cPanel: Application startup file = passenger_wsgi.py, Application Entry point = application.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import app as application  # noqa: E402
