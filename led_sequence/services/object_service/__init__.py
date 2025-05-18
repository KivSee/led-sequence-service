import aiohttp

class ObjectService:

    def __init__(self, host: str, port: int):
        self.base_url = f'http://{host}:{port}'
        self.session = None

    def __del__(self):
        if self.session:
            self.session.close()
    
    async def get_thing_proto_manifest(self, thing_name: str):
        if not self.session:
            self.session = aiohttp.ClientSession(base_url=self.base_url)
            
        headers = {'Accept': 'application/x-protobuf'}
        async with self.session.get(f'/thing/{thing_name}', headers=headers) as response:
            if response.status != 200:
                print(response)
                raise Exception(f'Failed to get proto manifest for thing {thing_name}')
            return await response.read()


