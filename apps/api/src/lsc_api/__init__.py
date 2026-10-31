"""lsc_api: FastAPI backend for the LSC Interpreter.

Modular monolith (structure.md). One API service; feature modules sit behind
router -> service -> repository -> infra boundaries so interpretation and
signaling can be split into separate services later without changing contracts.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
