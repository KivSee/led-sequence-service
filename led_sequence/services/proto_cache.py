"""Serve each thing's sequence as protobuf without converting it again on every request.

Converting a thing's JSON to protobuf (ParseDict + SerializeToString) runs in pure
Python on the Pi and takes up to ~0.6 s for a large song. When a trigger starts, all
rings ask at once and the service answered them one by one, so the last ring waited
over 10 s. Conversions now run in a small process pool (in parallel, off the event
loop) and the bytes are kept per sequence version, so each part is converted once.
"""
import asyncio
import logging
import os
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

from proto.effects_pb2 import AnimationProto
from google.protobuf.json_format import ParseDict


class ConversionError(Exception):
    """A thing config that is not a valid AnimationProto (message is ParseDict's)."""


def to_proto_bytes(thing_config) -> bytes:
    # runs in a worker process
    try:
        return ParseDict(thing_config, AnimationProto()).SerializeToString()
    except Exception as err:
        raise ConversionError(str(err)) from None


class ProtoCache:

    def __init__(self, workers: int):
        self._workers = workers
        self._pool = None
        # trigger name -> (sequence guid, {position: Future[bytes]}); only the latest version is kept
        self._entries = {}

    def start(self):
        if self._pool is None:
            self._pool = ProcessPoolExecutor(max_workers=self._workers)

    def shutdown(self):
        if self._pool is not None:
            self._pool.shutdown(cancel_futures=True)
            self._pool = None

    async def _convert(self, thing_config) -> bytes:
        self.start()
        try:
            return await asyncio.get_running_loop().run_in_executor(self._pool, to_proto_bytes, thing_config)
        except BrokenProcessPool:
            # a worker died (e.g. out of memory): start a fresh pool and convert here this time
            logging.warning("protobuf worker pool broke, restarting it")
            self._pool = None
            return to_proto_bytes(thing_config)

    def _entry(self, trigger_name: str, guid):
        entry = self._entries.get(trigger_name)
        if entry is None or entry[0] != guid:
            entry = (guid, {})
            self._entries[trigger_name] = entry
        return entry[1]

    async def get(self, trigger_name: str, guid, position: str, thing_config) -> bytes:
        """Protobuf bytes of one position's part; concurrent requests for it share one conversion."""
        parts = self._entry(trigger_name, guid)
        future = parts.get(position)
        if future is None:
            future = asyncio.ensure_future(self._convert(thing_config))
            parts[position] = future

            def forget_failure(done):
                if not done.cancelled() and done.exception() is not None and parts.get(position) is done:
                    del parts[position]
            future.add_done_callback(forget_failure)
        # shield: one ring dropping its connection must not cancel the conversion the others wait for
        return await asyncio.shield(future)

    async def convert_all(self, thing_configs: dict) -> dict:
        """Convert several things in parallel (validating them); raises ConversionError on the first invalid one."""
        positions = list(thing_configs)
        results = await asyncio.gather(*(self._convert(thing_configs[p]) for p in positions))
        return dict(zip(positions, results))

    def store(self, trigger_name: str, guid, converted: dict, unchanged=()):
        """Keep already converted parts for a new sequence version, so its first play needs no conversion.
        Parts listed in `unchanged` carry over from the previous version (an upload of a single thing)."""
        previous = self._entries.get(trigger_name)
        parts = self._entry(trigger_name, guid)
        if previous is not None and previous[1] is not parts:
            for position in unchanged:
                future = previous[1].get(position)
                if future is not None and future.done() and not future.cancelled() and future.exception() is None:
                    parts[position] = future
        loop = asyncio.get_running_loop()
        for position, body in converted.items():
            future = loop.create_future()
            future.set_result(body)
            parts[position] = future


proto_cache = ProtoCache(workers=int(os.environ.get('PROTO_WORKERS', '3')))
