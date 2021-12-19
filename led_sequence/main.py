import aiohttp
import os
import logging
from routes import setup_routes

app = aiohttp.web.Application()
setup_routes(app)

if __name__ == '__main__':
    server_port = os.environ.get('SERVER_PORT', 8082)
    LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
    logging.basicConfig(level=LOGLEVEL)
    aiohttp.web.run_app(app, port=server_port)
