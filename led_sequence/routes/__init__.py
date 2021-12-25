import aiohttp
from aiohttp import web
import json
import logging
import os
import asyncio
from services.storage import create_storage_backend

# TODO: how to properly resolve proto import?
import sys
sys.path.append(os.path.join(sys.path[0],'proto'))
from proto.effects_pb2 import AnimationProto
from google.protobuf.json_format import ParseDict

storage_backend = create_storage_backend()

async def get_guid(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    trigger_seq_config = await storage_backend.read(trigger_name)
    if not trigger_seq_config:
        return aiohttp.web.Response(status=404)
    current_guid = str(trigger_seq_config['guid'])
    return aiohttp.web.json_response({"guid": current_guid})

async def get_sequence(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    thing_name = request.match_info.get('thing_name')
    guid = request.match_info.get('guid')
    trigger_seq_config = await storage_backend.read(trigger_name)
    if not trigger_seq_config:
        return aiohttp.web.Response(status=404)

    current_guid = str(trigger_seq_config['guid'])
    if guid and guid != current_guid:
        return aiohttp.web.Response(status=404)

    etag = current_guid
    if request.headers.get('if-none-match') == etag:
        return aiohttp.web.Response(status=304)

    thing_config = trigger_seq_config['things'].get(thing_name)

    if thing_config == None:
        return aiohttp.web.Response(status=404)

    headers = {
        'etag': etag
    }
    accept_content_type = request.headers.get('accept')
    if accept_content_type == 'application/x-protobuf':
        message = ParseDict(thing_config, AnimationProto())
        return aiohttp.web.Response(body = message.SerializeToString(), headers=headers)
    if accept_content_type == 'application/json' or accept_content_type == '*/*':
        return aiohttp.web.json_response(thing_config, headers=headers)
    return aiohttp.web.Response(status=400)

async def set_sequence(request):

    trigger_name = request.match_info.get('trigger_name')
    thing_name = request.match_info.get('thing_name')

    [new_config, curr_conf] = await asyncio.gather(request.json(), storage_backend.read(trigger_name))
    if not curr_conf:
        curr_conf = {
            "things": {},
            "guid": ""
        }

    try: 
        if thing_name:
            curr_conf['things'][thing_name] = new_config
            ParseDict(new_config, AnimationProto())
        else:
            curr_conf['things'] = new_config
            for single_thing_config in new_config.values():
                ParseDict(single_thing_config, AnimationProto())
    except Exception as err:
        return aiohttp.web.Response(status=400, text = str(err))

    del curr_conf['guid']
    guid = hash(json.dumps(curr_conf)) & 0xffffffff
    curr_conf['guid'] = guid
    await storage_backend.upsert(trigger_name, curr_conf)
    logging.info("saved new sequence for trigger '%s' on thing '%s' with guid '%d'", trigger_name, thing_name, guid)

    headers = {
        'etag': str(guid)
    }
    return aiohttp.web.Response(status=200, headers=headers)

def setup_routes(app):
    app.router.add_get('/triggers/{trigger_name}/guid', get_guid),
    app.router.add_get('/triggers/{trigger_name}/objects/{thing_name}', get_sequence),
    app.router.add_get('/triggers/{trigger_name}/objects/{thing_name}/guid/{guid}', get_sequence),
    app.router.add_put('/triggers/{trigger_name}/objects/{thing_name}', set_sequence),
    app.router.add_put('/triggers/{trigger_name}', set_sequence),
