import os
import asyncio
from src.utils.config import config
from motor.motor_asyncio import AsyncIOMotorClient

class ForkSafeDatabase:
    def __init__(self):
        self._clients = {}

    def _get_db(self):
        pid = os.getpid()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        key = (pid, loop)
        if key not in self._clients:
            print(f"[ForkSafeDatabase] Initializing client for PID {pid} and Loop {loop}")
            client = AsyncIOMotorClient(config.database_url)
            self._clients[key] = client.get_default_database()

        return self._clients[key]

    def __getitem__(self, name):
        return self._get_db()[name]

    def __getattr__(self, name):
        return getattr(self._get_db(), name)

db = ForkSafeDatabase()
