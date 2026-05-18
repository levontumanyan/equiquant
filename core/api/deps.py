from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository

db_manager = DatabaseManager()
repo = DatabaseRepository(db_manager)
