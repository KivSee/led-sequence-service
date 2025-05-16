import time
import aiohttp
from aiohttp import web
import os
import logging
from routes import setup_routes

async def timing_middleware(app, handler):
    async def middleware_handler(request):
        start_time = time.monotonic()
        try:
            response = await handler(request)
            return response
        finally:
            duration = time.monotonic() - start_time
            logging.info("Request %s %s took %.6f seconds", request.method, request.path, duration)
    return middleware_handler

app = aiohttp.web.Application(
    middlewares=[timing_middleware],
    client_max_size=16 * 1024 * 1024,  # 16MB
)
setup_routes(app)

if __name__ == '__main__':
    server_port = int(os.environ.get('SERVER_PORT', 8082))
    LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
    logging.basicConfig(level=LOGLEVEL)
    aiohttp.web.run_app(app, port=server_port)
