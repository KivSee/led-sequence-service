from typing import List
from services.storage.storage import StorageInterface
import os
import json
import aiofiles as aiof

class GitStorage(StorageInterface):

    def __init__(self, repo: str):
        self.sequences_dir = os.path.join(repo, 'sequences')
        self.config_dir = os.path.join(repo, 'config')

        try:
            os.mkdir(self.sequences_dir)
        except FileExistsError:
            pass

        try:
            os.mkdir(self.config_dir)
        except FileExistsError:
            pass

    async def upsert_config(self, trigger_name: str, config):
        file_name = self.trigger_name_to_config_file_name(trigger_name)
        async with aiof.open(file_name, "w") as out:
            await out.write(json.dumps(config))
            await out.flush()

    async def read_config(self, trigger_name: str):
        file_name = self.trigger_name_to_config_file_name(trigger_name)
        try:
            async with aiof.open(file_name, "r") as out:
                return json.loads(await out.read())
        except FileNotFoundError:
            return None

    async def upsert_sequence(self, trigger_name: str, config):
        file_name = self.trigger_name_to_sequence_file_name(trigger_name)
        async with aiof.open(file_name, "w") as out:
            await out.write(json.dumps(config))
            await out.flush()

    async def read_sequence(self, trigger_name: str):
        file_name = self.trigger_name_to_sequence_file_name(trigger_name)
        try:
            async with aiof.open(file_name, "r") as out:
                return json.loads(await out.read())
        except FileNotFoundError:
            return None

    async def get_all_triggers(self) -> List[str]:
        return []

    def trigger_name_to_sequence_file_name(self, trigger_name: str) -> str:
        return os.path.join(self.sequences_dir, trigger_name + '.json')
    
    def trigger_name_to_config_file_name(self, trigger_name: str) -> str:
        return os.path.join(self.config_dir, trigger_name + '.json')
