"""Feature modules.

Each module follows the same shape (structure.md):
    router.py · schemas.py · service.py · repository.py · domain.py
Modules never import another module's repository; they call its service
interface. Routers hold no business rules.

Planned modules (added by their specs): identity, consent, billing, models,
community, privacy, admin, audit, messaging (P2), calls (P3).
"""
