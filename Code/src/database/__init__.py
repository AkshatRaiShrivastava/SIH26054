"""
Database layer for Digital Twin Pipeline.

Modules:
- database: SQLite schema, connections, and initialization

Usage:
    from src.database.database import init_database, get_connection
    # or
    from src.database import database
    database.init_database()
"""

# Database module is available but not imported at package level
# to avoid circular dependencies
# Users should import directly: from src.database.database import ...

__all__ = ["database"]
