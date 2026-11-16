"""Shared set-up for the tests: make the app's modules importable from any folder, on Windows or not.

The tests cover logic only (what counts as a yes, which folders are personal, how a cut-off AI reply is handled).
Nothing here touches real files, the registry, the network or an AI service.
"""

import importlib
import os
import sys
import types

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP not in sys.path:
    sys.path.insert(0, APP)


def load(name):
    """Import an app module; where it can't load (a Windows-only module on another system) use an empty stand-in."""
    try:
        return importlib.import_module(name)
    except Exception:
        sys.modules[name] = types.ModuleType(name)
        return sys.modules[name]
