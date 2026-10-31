"""Infrastructure adapters, each behind a Protocol.

External services are injected through these Protocols so they can be swapped
(structure.md). Concrete GCP implementations are added when a module needs them;
W01 defines only the interfaces the core and modules depend on.
"""
