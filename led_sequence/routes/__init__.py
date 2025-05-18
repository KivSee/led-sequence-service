import time
import aiohttp
import json
import logging
import os
import asyncio
import kivsee_render
from services.object_service import ObjectService
from services.audacity import config_to_audacity_labels_beats
from services.audacity import config_to_audacity_labels_episodes
from services.storage import create_storage_backend

# TODO: how to properly resolve proto import?
import sys
sys.path.append(os.path.join(sys.path[0],'proto'))
from proto.effects_pb2 import AnimationProto
from google.protobuf.json_format import ParseDict

storage_backend = create_storage_backend()

# Get object service configuration from environment variables
object_service_host = os.environ.get('LED_OBJECT_SERVICE_IP')
if not object_service_host:
    raise Exception('LED_OBJECT_SERVICE_IP environment variable must be set')
object_service_port = int(os.environ.get('LED_OBJECT_SERVICE_PORT', '8081'))
object_service = ObjectService(host=object_service_host, port=object_service_port)

# Get the directory where this file is located
CURRENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RING1_PROTO_PATH = os.path.join(CURRENT_DIR, 'ring1_proto')

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

async def get_trigger_stats(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    # Get start_time and end_time from query parameters, default to 0 and 1000 if not provided
    try:
        start_time = int(request.query.get('start_time', '0'))
        end_time = int(request.query.get('end_time', '1000'))
    except ValueError:
        return aiohttp.web.Response(status=400, text="start_time and end_time must be valid numbers")

    if start_time >= end_time:
        return aiohttp.web.Response(status=400, text="start_time must be less than end_time")

    trigger_seq_config = await storage_backend.read_sequence(trigger_name)
    if not trigger_seq_config:
        return aiohttp.web.Response(status=404)

    # First create all controllers
    NUM_LEDS = 144
    controllers = []
    for thing_name, thing_config in trigger_seq_config['things'].items():

        try:
            ring_proto_data = await object_service.get_thing_proto_manifest(thing_name)
        except Exception as e:
            return aiohttp.web.Response(status=500, text=f"Error fetching proto data: {str(e)}")

        message = ParseDict(thing_config, AnimationProto())
        serialized_message = message.SerializeToString()
        controller = kivsee_render.LedController(NUM_LEDS)
        controller.init_from_proto_buffers(serialized_message, ring_proto_data)
        controllers.append(controller)

    total_brightness = 0
    total_pixels = 0
    frame_count = 0
    
    # Single loop over time for all controllers
    current_time = start_time
    while current_time <= end_time:
        frame_count += 1
        # Process each controller for this time step
        for controller in controllers:
            buf = controller.render(current_time)
            # Sum brightness for all LEDs in this frame
            for hsv_tuple in buf:
                total_brightness += hsv_tuple[2]  # V value is at index 2
                total_pixels += 1
                
        current_time += 20  # 20ms increment
    
    avg_brightness = total_brightness / total_pixels if total_pixels > 0 else 0
    
    stats = {
        "guid": str(trigger_seq_config['guid']),
        "num_things": len(trigger_seq_config['things']),
        "average_brightness": float(avg_brightness),
        "start_time": start_time,
        "end_time": end_time,
        "frame_count": frame_count,
        "total_pixels_processed": total_pixels
    }
    return aiohttp.web.json_response(stats)

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
    app.router.add_get('/triggers/{trigger_name}/stats', get_trigger_stats),

