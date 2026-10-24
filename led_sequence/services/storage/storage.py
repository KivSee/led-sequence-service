from typing import List
import abc

class StorageInterface(metaclass=abc.ABCMeta):
    
    @abc.abstractmethod
    async def upsert_config(self, trigger_name: str, config):
        """ Create or update new trigger configuration for a specific trigger
        """

    @abc.abstractmethod
    async def read_config(self, trigger_name: str):
        """ Read trigger configuration
        """

    @abc.abstractmethod
    async def upsert_sequence(self, trigger_name: str, config):
        """ Create or update new sequence configuration for a specific trigger
        """

    @abc.abstractmethod
    async def read_sequence(self, trigger_name: str):
        """ Read trigger up-to-date sequence configuration
        """

    @abc.abstractmethod
    async def get_all_triggers(self) -> List[str]:
        """ return all configured triggers
        """

    @abc.abstractmethod
    async def read_placement(self):
        """ Read the ring placement (position -> physical ring), {} when none is set
        """

    @abc.abstractmethod
    async def upsert_placement(self, placement):
        """ Replace the ring placement, keeping the previous one as a backup
        """
