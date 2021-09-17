from typing import List
import abc

class StorageInterface(metaclass=abc.ABCMeta):
    
    @abc.abstractmethod
    async def upsert(self, trigger_name: str, config):
        """ Create or update new sequence configuration for a specific trigger
        """

    @abc.abstractmethod
    async def read(self, trigger_name: str):
        """ Read trigger configuration
        """

    @abc.abstractmethod
    async def get_all_triggers(self) -> List[str]:
        """ return all configured triggers
        """
