"""Global test isolation."""
import os

# Unit tests must not export spans or depend on a running local collector.
os.environ["PHOENIX_ENABLED"] = "false"

