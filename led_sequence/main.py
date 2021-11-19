from aiohttp import web
import aiohttp
import os
import json
import logging
import asyncio

# TODO: how to properly resolve proto import?
import sys
sys.path.append(os.path.join(sys.path[0],'proto'))
from proto.effects_pb2 import AnimationProto
from google.protobuf.json_format import ParseDict

from services.storage import create_storage_backend

storage_backend = create_storage_backend()

async def get_guid(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    trigger_seq_config = await storage_backend.read(trigger_name)
    if not trigger_seq_config:
        return web.Response(status=404)
    current_guid = str(trigger_seq_config['guid'])
    return web.json_response({"guid": current_guid})

async def get_sequence(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    thing_name = request.match_info.get('thing_name')
    guid = request.match_info.get('guid')
    trigger_seq_config = await storage_backend.read(trigger_name)
    if not trigger_seq_config:
        return web.Response(status=404)

    current_guid = str(trigger_seq_config['guid'])
    if guid and guid != current_guid:
        return web.Response(status=404)

    etag = current_guid
    if request.headers.get('if-none-match') == etag:
        return web.Response(status=304)

    thing_config = trigger_seq_config['things'].get(thing_name)

    if thing_config == None:
        return web.Response(status=404)

    headers = {
        'etag': etag
    }
    accept_content_type = request.headers.get('accept')
    if accept_content_type == 'application/x-protobuf':
        message = ParseDict(thing_config, AnimationProto())
        return web.Response(body = message.SerializeToString(), headers=headers)
    if accept_content_type == 'application/json' or accept_content_type == '*/*':
        return web.json_response(thing_config, headers=headers)
    return web.Response(status=400)

async def set_sequence(request):

    trigger_name = request.match_info.get('trigger_name')
    thing_name = request.match_info.get('thing_name')

    [new_config, curr_conf] = await asyncio.gather(request.json(), storage_backend.read(trigger_name))
    if not curr_conf:
        curr_conf = {
            "things": {},
            "guid": ""
        }

    if thing_name:
        curr_conf['things'][thing_name] = new_config
    else:
        curr_conf['things'] = new_config

    del curr_conf['guid']
    guid = hash(json.dumps(curr_conf)) & 0xffffffff
    curr_conf['guid'] = guid
    await storage_backend.upsert(trigger_name, curr_conf)
    logging.info("saved new sequence for trigger '%s' on thing '%s' with guid '%d'", trigger_name, thing_name, guid)

    headers = {
        'etag': str(guid)
    }
    return web.Response(status=200, headers=headers)

app = web.Application()
app.add_routes([
    web.get('/triggers/{trigger_name}/guid', get_guid),
    web.get('/triggers/{trigger_name}/objects/{thing_name}', get_sequence),
    web.get('/triggers/{trigger_name}/objects/{thing_name}/guid/{guid}', get_sequence),
    web.put('/triggers/{trigger_name}/objects/{thing_name}', set_sequence),
    web.put('/triggers/{trigger_name}', set_sequence),
    ])

if __name__ == '__main__':
    server_port = os.environ.get('SERVER_PORT', 8082)
    LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
    logging.basicConfig(level=LOGLEVEL)
    web.run_app(app, port=server_port)
