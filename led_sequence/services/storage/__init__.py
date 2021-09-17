from services.storage.git import GitStorage
import os

def create_storage_backend():
    storage_type = os.environ.get('STORAGE_TYPE')
    if storage_type == 'git':
        repo = os.environ.get('GIT_STORAGE_REPO')
        if repo == None:
            raise Exception('storage type GIT requires git repo')
        
        return GitStorage(repo)
    
    raise Exception('unsupported STORAGE_TYPE', storage_type)
