import time
import aiohttp
from aiohttp import web
import json
import logging
import os
import asyncio
from services.audacity import config_to_audacity_labels_beats
from services.audacity import config_to_audacity_labels_episodes
from services.storage import create_storage_backend

# TODO: how to properly resolve proto import?
import sys
sys.path.append(os.path.join(sys.path[0],'proto'))
from proto.effects_pb2 import AnimationProto
from google.protobuf.json_format import ParseDict

storage_backend = create_storage_backend()

async def put_trigger_config(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    config = await request.json()
    await storage_backend.upsert_config(trigger_name, config)
    return aiohttp.web.Response(status=200)

async def get_trigger_config(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    trigger_config = await storage_backend.read_config(trigger_name)
    if not trigger_config:
        return aiohttp.web.Response(status=404)
    return aiohttp.web.json_response(trigger_config)

async def get_audacity_episodes(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    trigger_config = await storage_backend.read_config(trigger_name)
    if not trigger_config:
        return aiohttp.web.Response(status=404)
    audacity_labels = config_to_audacity_labels_episodes(trigger_config)
    return aiohttp.web.Response(text=audacity_labels)

async def get_audacity_beats(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    trigger_config = await storage_backend.read_config(trigger_name)
    if not trigger_config:
        return aiohttp.web.Response(status=404)
    audacity_labels = config_to_audacity_labels_beats(trigger_config)
    return aiohttp.web.Response(text=audacity_labels)

async def get_guid(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    trigger_seq_config = await storage_backend.read_sequence(trigger_name)
    if not trigger_seq_config:
        return aiohttp.web.Response(status=404)
    current_guid = str(trigger_seq_config['guid'])
    return aiohttp.web.json_response({"guid": current_guid})

async def get_all_triggers(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    trigger_seq_config = await storage_backend.read_sequence(trigger_name)
    if not trigger_seq_config:
        return aiohttp.web.Response(status=404)
    headers = {
        'etag': str(trigger_seq_config['guid'])
    }
    return aiohttp.web.json_response(trigger_seq_config["things"], headers = headers)

async def get_sequence(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    thing_name = request.match_info.get('thing_name')
    guid = request.match_info.get('guid')
    storage_start_time = time.perf_counter()
    trigger_seq_config = await storage_backend.read_sequence(trigger_name)
    storage_end_time = time.perf_counter()
    logging.debug("storage read took %.6f seconds", storage_end_time - storage_start_time)
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
        proto_start_time = time.perf_counter()
        serialized_message = message.SerializeToString()
        proto_end_time = time.perf_counter()
        logging.debug("protobuf serialization took %.6f seconds", proto_end_time - proto_start_time)
        return aiohttp.web.Response(body = serialized_message, headers=headers)
    if accept_content_type == 'application/json' or accept_content_type == '*/*':
        return aiohttp.web.json_response(thing_config, headers=headers)
    return aiohttp.web.Response(status=400)

async def set_sequence(request):

    trigger_name = request.match_info.get('trigger_name')
    thing_name = request.match_info.get('thing_name')

    [new_config, curr_conf] = await asyncio.gather(request.json(), storage_backend.read_sequence(trigger_name))
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
    await storage_backend.upsert_sequence(trigger_name, curr_conf)
    logging.info("saved new sequence for trigger '%s' on thing '%s' with guid '%d'", trigger_name, thing_name, guid)

    headers = {
        'etag': str(guid)
    }
    return aiohttp.web.Response(status=200, headers=headers)

def setup_routes(app):
    app.router.add_put('/triggers/{trigger_name}/config', put_trigger_config),
    app.router.add_get('/triggers/{trigger_name}/config', get_trigger_config),
    app.router.add_get('/triggers/{trigger_name}/config/audacity/episodes', get_audacity_episodes),
    app.router.add_get('/triggers/{trigger_name}/config/audacity/beats', get_audacity_beats),
    app.router.add_get('/triggers/{trigger_name}/guid', get_guid),
    app.router.add_get('/triggers/{trigger_name}', get_all_triggers),
    app.router.add_get('/triggers/{trigger_name}/objects/{thing_name}', get_sequence),
    app.router.add_get('/triggers/{trigger_name}/objects/{thing_name}/guid/{guid}', get_sequence),
    app.router.add_put('/triggers/{trigger_name}/objects/{thing_name}', set_sequence),
    app.router.add_put('/triggers/{trigger_name}', set_sequence),
