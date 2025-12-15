import time
import aiohttp
from aiohttp import web
import os
import logging
from routes import setup_routes

async def cors_middleware(app, handler):
    async def middleware_handler(request):
        # Handle preflight requests
        if request.method == 'OPTIONS':
            return web.Response(
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': '*',
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Max-Age': '3600',
                }
            )
        
        response = await handler(request)
        
        # Add CORS headers to all responses
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = '*'
        response.headers['Access-Control-Allow-Headers'] = '*'
        
        return response
    return middleware_handler

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
    middlewares=[cors_middleware, timing_middleware],
    client_max_size=16 * 1024 * 1024,  # 16MB
)
setup_routes(app)

if __name__ == '__main__':
    server_port = int(os.environ.get('SERVER_PORT', 8082))
    LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
    logging.basicConfig(level=LOGLEVEL)
    aiohttp.web.run_app(app, port=server_port)
