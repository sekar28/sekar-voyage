"""Moved to shared/sekar_common/secrets_store.py; this alias keeps `import secrets_store` working."""
import importlib
import os
import sys

_shared = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
if _shared not in sys.path:
    sys.path.insert(0, _shared)
sys.modules[__name__] = importlib.import_module("sekar_common.secrets_store")
