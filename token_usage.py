"""Measured AI usage per pipeline stage; cached assets do not incur new usage."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
from urllib.error import HTTPError

_collector = ContextVar('token_usage_collector', default=None)
_phase = ContextVar('token_usage_phase', default=None)
FIELDS = ('input_tokens', 'output_tokens', 'cached_input_tokens')


def empty_usage():
    return {**dict.fromkeys((*FIELDS, 'total_tokens'), 0),
            'requests': 0, 'unknown_requests': 0}


def measured_usage(value):
    if (not isinstance(value, dict)
            or any(type(value.get(k)) is not int or value[k] < 0 for k in FIELDS)
            or value['cached_input_tokens'] > value['input_tokens']):
        return None
    return {**{k: value[k] for k in FIELDS},
            'total_tokens': value['input_tokens'] + value['output_tokens']}


@contextmanager
def collect_usage(directory, stage, emit, *, phase_ids=()):
    """Persist before emitting absolute totals, so polling/retries cannot double count."""
    path = directory / 'token_usage.json'
    stages = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    row = stages.setdefault(stage, empty_usage())
    if phase_ids:
        phases = row.setdefault('phases', {})
        for phase_id in phase_ids:
            phases.setdefault(str(phase_id), empty_usage())
        row.setdefault('shared', empty_usage())

    def publish():
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(stages, indent=2), encoding='utf-8')
        temporary.replace(path)
        emit(tokenUsage=stages)

    def record(value, *, initialize=False):
        row = stages[stage]
        phase_id = _phase.get()
        detail = (row.setdefault('phases', {}).setdefault(phase_id, empty_usage())
                  if phase_id is not None else row.setdefault('shared', empty_usage()))
        if initialize:
            publish()
            return
        measured = measured_usage(value)
        for target in (row, detail):
            target['requests'] += 1
            if measured is None:
                target['unknown_requests'] += 1
            else:
                for key, count in measured.items():
                    target[key] += count
        publish()

    token = _collector.set(record)
    try:
        publish()
        yield
    finally:
        _collector.reset(token)


@contextmanager
def phase_usage(phase_id):
    """Attribute requests and retries to the script's phase ID, not its list index."""
    token = _phase.set(str(phase_id))
    try:
        record = _collector.get()
        if record:
            record(None, initialize=True)
        yield
    finally:
        _phase.reset(token)


@contextmanager
def track_request():
    """Count even responses rejected by validators or returned as HTTP errors."""
    record = _collector.get()
    value = None

    def observe(payload):
        nonlocal value
        value = payload.get('usage') if isinstance(payload, dict) else None

    try:
        yield observe
    except HTTPError as error:
        if record:
            try:
                observe(json.loads(error.read(65536)))
            except (OSError, ValueError):
                pass
        raise
    finally:
        if record:
            record(value)
