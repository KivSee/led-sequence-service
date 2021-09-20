from aiohttp import web
import aiohttp
import os
import json

# TODO: how to properly resolve proto import?
import sys
sys.path.append(os.path.join(sys.path[0],'proto'))
from proto.effects_pb2 import AnimationProto
from google.protobuf.json_format import ParseDict

from services.storage import create_storage_backend

storage_backend = create_storage_backend()

async def get_sequence(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    thing_name = request.match_info.get('thing_name')
    guid = request.match_info.get('guid')
    trigger_seq_config = await storage_backend.read(trigger_name)

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

    new_config = await request.json()
    if thing_name:
        curr_conf = {
            "things": {},
            "guid": ""
        }
        try:
            curr_conf = await storage_backend.read(trigger_name)
        except:
            pass
        curr_conf['things'][thing_name] = new_config
        del curr_conf['guid']
        guid = hash(json.dumps(curr_conf)) & 0xffffffff
        curr_conf['guid'] = guid
        await storage_backend.upsert(trigger_name, curr_conf)

        headers = {
            'etag': str(guid)
        }

        return web.Response(status=200, headers=headers)

app = web.Application()
app.add_routes([
    web.get('/triggers/{trigger_name}/objects/{thing_name}', get_sequence),
    web.get('/triggers/{trigger_name}/objects/{thing_name}/guid/{guid}', get_sequence),
    web.put('/triggers/{trigger_name}/objects/{thing_name}', set_sequence),
    ])

if __name__ == '__main__':
    server_port = os.environ.get('SERVER_PORT', 8082)
    web.run_app(app, port=server_port)
