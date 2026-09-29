"""Container liveness check based on the worker's recent poll heartbeat."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

path = Path(os.getenv("LBOE_WORKER_HEARTBEAT", "/tmp/lboe-worker-heartbeat"))
max_age = int(os.getenv("LBOE_WORKER_HEALTH_MAX_AGE", "30"))
if not path.exists() or time.time() - path.stat().st_mtime > max_age:
    sys.exit(1)
