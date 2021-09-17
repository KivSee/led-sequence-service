from typing import List
from services.storage.storage import StorageInterface
import os
import json
import aiofiles as aiof

class GitStorage(StorageInterface):

    def __init__(self, repo: str):
        self.repo = repo

    async def upsert(self, trigger_name: str, config):
        file_name = self.trigger_name_to_file_name(trigger_name)
        async with aiof.open(file_name, "w") as out:
            await out.write(json.dumps(config))
            await out.flush()

    async def read(self, trigger_name: str):
        file_name = self.trigger_name_to_file_name(trigger_name)
        async with aiof.open(file_name, "r") as out:
            return json.loads(await out.read())

    async def get_all_triggers(self) -> List[str]:
        return []

    def trigger_name_to_file_name(self, trigger_name: str) -> str:
        return os.path.join(self.repo, trigger_name + '.json')