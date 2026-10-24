from typing import List
from services.storage.storage import StorageInterface
import os
import json
import aiofiles as aiof

class GitStorage(StorageInterface):

    def __init__(self, repo: str):
        self.sequences_dir = os.path.join(repo, 'sequences')
        self.config_dir = os.path.join(repo, 'config')
        self.placement_dir = os.path.join(repo, 'placement')
        self.placement_file = os.path.join(self.placement_dir, 'rings.json')
        self.placement_prev_file = os.path.join(self.placement_dir, 'rings.prev.json')

        for directory in (self.sequences_dir, self.config_dir, self.placement_dir):
            try:
                os.mkdir(directory)
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

    async def read_placement(self):
        try:
            async with aiof.open(self.placement_file, "r") as f:
                return json.loads(await f.read())
        except FileNotFoundError:
            return {}

    async def upsert_placement(self, placement):
        # keep the previous placement next to it so a wrong save can be undone,
        # and write via a temp file so a reader never sees a half-written file
        if os.path.exists(self.placement_file):
            os.replace(self.placement_file, self.placement_prev_file)
        tmp_file = self.placement_file + '.tmp'
        async with aiof.open(tmp_file, "w") as f:
            await f.write(json.dumps(placement, indent=2, sort_keys=True))
            await f.flush()
        os.replace(tmp_file, self.placement_file)

    def trigger_name_to_sequence_file_name(self, trigger_name: str) -> str:
        return os.path.join(self.sequences_dir, trigger_name + '.json')
    
    def trigger_name_to_config_file_name(self, trigger_name: str) -> str:
        return os.path.join(self.config_dir, trigger_name + '.json')
