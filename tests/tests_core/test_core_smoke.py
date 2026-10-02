
import importlib


# Only testing program import
def test_project_imports() -> None:
    importlib.import_module("companion4soloplayer")

# Only testing core import
def test_core_imports() -> None:
    importlib.import_module("companion4soloplayer.core")
