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
from services import placement as ring_placement

# TODO: how to properly resolve proto import?
import sys
sys.path.append(os.path.join(sys.path[0],'proto'))
from proto.effects_pb2 import AnimationProto
from google.protobuf.json_format import ParseDict

storage_backend = create_storage_backend()

LED_OBJECT_SERVICE_URL = os.environ.get('LED_OBJECT_SERVICE_URL', 'http://ledobjectservice:80')
TRIGGER_SERVICE_URL = os.environ.get('TRIGGER_SERVICE_URL', 'http://ledtriggerservice:80')
PLACEMENT_UI_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'placement.html')

# The trigger service asks for a trigger's guid every time it starts one, so the
# last name asked for is what is playing now; re-sending it applies a new placement.
last_trigger = {'name': None}

async def current_placement():
    return ring_placement.normalize(await storage_backend.read_placement())

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
    last_trigger['name'] = trigger_name
    placement = await current_placement()
    current_guid = str(ring_placement.combine_guid(trigger_seq_config['guid'], placement))
    return aiohttp.web.json_response({"guid": current_guid})

async def get_all_triggers(request: aiohttp.RequestInfo):
    trigger_name = request.match_info.get('trigger_name')
    trigger_seq_config = await storage_backend.read_sequence(trigger_name)
    if not trigger_seq_config:
        return aiohttp.web.Response(status=404)
    placement = await current_placement()
    headers = {
        'etag': str(ring_placement.combine_guid(trigger_seq_config['guid'], placement))
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

    placement = await current_placement()
    current_guid = str(ring_placement.combine_guid(trigger_seq_config['guid'], placement))
    if guid and guid != current_guid:
        return aiohttp.web.Response(status=404)

    etag = current_guid
    if request.headers.get('if-none-match') == etag:
        return aiohttp.web.Response(status=304)

    # a placed ring plays the part of the position it hangs at
    position = ring_placement.part_for(placement, thing_name)
    if position != thing_name:
        logging.debug("thing '%s' is placed at '%s'", thing_name, position)
    thing_config = trigger_seq_config['things'].get(position)

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

async def list_physical_things():
    """(rings, pendants) the object service knows (they have a segment map), sorted by number."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        async with session.get(f"{LED_OBJECT_SERVICE_URL}/thing", headers={'accept': 'application/json'}) as res:
            res.raise_for_status()
            things = await res.json()
    rings = sorted((n for n in things if ring_placement.RING_NAME.match(n)), key=ring_placement.ring_number)
    pendants = sorted((n for n in things if ring_placement.PENDANT_NAME.match(n)), key=ring_placement.ring_number)
    return rings, pendants

async def list_physical_rings():
    return (await list_physical_things())[0]

async def ensure_segment_maps(physical_rings):
    """Give rings without a segment map a copy of ring1's (all rings share the same map)."""
    known = set(await list_physical_rings())
    missing = [name for name in physical_rings if name not in known]
    if not missing:
        return []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        async with session.get(f"{LED_OBJECT_SERVICE_URL}/thing/ring1", headers={'accept': 'application/json'}) as res:
            res.raise_for_status()
            template = await res.json()
        for name in missing:
            config = {k: v for k, v in template.items() if k not in ('guid', 'thingName')}
            async with session.put(f"{LED_OBJECT_SERVICE_URL}/thing/{name}", json=config) as res:
                res.raise_for_status()
            logging.info("created segment map for '%s' from ring1", name)
    return missing

async def get_placement(request):
    placement = await current_placement()
    try:
        physical_rings, physical_pendants = await list_physical_things()
        object_service_error = None
    except Exception as err:
        physical_rings, physical_pendants = [], []
        object_service_error = f"could not list rings from the object service: {err}"
    return web.json_response({
        "placement": placement,
        "physicalRings": physical_rings,
        "physicalPendants": physical_pendants,
        "warnings": ring_placement.warnings(placement, physical_rings or None),
        "lastTrigger": last_trigger['name'],
        "objectServiceError": object_service_error,
    })

async def put_placement(request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"errors": ["body is not valid JSON"]}, status=400)
    raw = body.get('placement', body) if isinstance(body, dict) else body
    placement, errors = ring_placement.validate(raw)
    if errors:
        return web.json_response({"errors": errors}, status=400)
    await storage_backend.upsert_placement(placement)
    logging.info("saved ring placement %s", placement)
    try:
        created = await ensure_segment_maps(sorted(set(placement['rings'].values())))
        segment_error = None
    except Exception as err:
        created = []
        segment_error = f"placement saved, but segment maps could not be checked: {err}"
    try:
        physical_rings = await list_physical_rings()
    except Exception:
        physical_rings = None
    return web.json_response({
        "placement": placement,
        "warnings": ring_placement.warnings(placement, physical_rings),
        "createdSegmentMaps": created,
        "segmentMapError": segment_error,
        "lastTrigger": last_trigger['name'],
    })

async def apply_placement(request):
    """Re-send the current trigger so the rings fetch their part with the new placement."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    name = (body or {}).get('trigger') or last_trigger['name']
    if not name:
        return web.json_response({"error": "no trigger has been started since the service started"}, status=409)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        async with session.post(f"{TRIGGER_SERVICE_URL}/trigger/{name}") as res:
            text = await res.text()
            if res.status >= 400:
                return web.json_response({"error": f"trigger service: HTTP {res.status} {text[:200]}"}, status=502)
    return web.json_response({"trigger": name})

async def placement_ui(request):
    return web.FileResponse(PLACEMENT_UI_FILE)

def setup_routes(app):
    app.router.add_get('/placement', get_placement),
    app.router.add_put('/placement', put_placement),
    app.router.add_post('/placement/apply', apply_placement),
    app.router.add_get('/placement/ui', placement_ui),
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
