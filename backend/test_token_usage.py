"""Usage survives retries and counts only requests actually sent to AI."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from token_usage import collect_usage, track_request
import plant_kurzge as planner
from backend.graphics_worker import run as run_graphics
from backend.test_graphics import graphics_script, png_response
from render_style import load_render_style

MEASURED = {'input_tokens': 120, 'cached_input_tokens': 80, 'output_tokens': 30}


class TokenUsageTests(unittest.TestCase):
    def test_counts_validation_retries_and_keeps_stage_totals_across_workers(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for stage in ('graphics', 'animation', 'animation'):
                with collect_usage(output, stage, lambda **e: events.append(json.loads(json.dumps(e)))):
                    with track_request() as observe:
                        observe({'usage': MEASURED})
            saved = json.loads((output / 'token_usage.json').read_text())
            self.assertEqual(saved['graphics']['total_tokens'], 150)
            self.assertEqual(saved['animation']['input_tokens'], 240)
            self.assertEqual(saved['animation']['output_tokens'], 60)
            self.assertEqual(saved['animation']['total_tokens'], 300)
            self.assertEqual(saved['animation']['requests'], 2)
            self.assertEqual(events[-1]['tokenUsage'], saved)

    def test_invalid_text_result_and_http_errors_still_record_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with collect_usage(output, 'script', lambda **e: None):
                with patch('plant_kurzge.urlopen', return_value=io.BytesIO(json.dumps(
                        {'success': False, 'usage': MEASURED}).encode())):
                    with self.assertRaises(ValueError):
                        planner.request_text('test', api_url='http://fixture', api_key='fixture', model='fixture')
                error = HTTPError('http://fixture', 502, 'Failed', {}, io.BytesIO(json.dumps({'usage': MEASURED}).encode()))
                with patch('plant_kurzge.urlopen', side_effect=error):
                    with self.assertRaises(HTTPError):
                        planner.request_text('test', api_url='http://fixture', api_key='fixture', model='fixture')
            row = json.loads((output / 'token_usage.json').read_text())['script']
            self.assertEqual((row['requests'], row['unknown_requests'], row['total_tokens']), (2, 0, 300))

    def test_unknown_usage_is_not_reported_as_measured_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with collect_usage(output, 'script', lambda **e: None):
                for value in (None, {}, {**MEASURED, 'input_tokens': True}, {**MEASURED, 'output_tokens': -1}):
                    with track_request() as observe:
                        observe({'usage': value})
                with self.assertRaises(URLError):
                    with track_request():
                        raise URLError('offline')
            row = json.loads((output / 'token_usage.json').read_text())['script']
            self.assertEqual(row['requests'], 5)
            self.assertEqual(row['unknown_requests'], 5)

    def test_image_worker_persists_usage_and_cache_does_not_add_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'kich_ban.json').write_text(json.dumps(graphics_script()))
            (output / 'render_config.json').write_text(json.dumps(load_render_style('flat')))
            payload = json.loads(png_response())
            payload['usage'] = MEASURED
            from contextlib import redirect_stdout
            with patch('image_asset_generator.urlopen', side_effect=lambda *a, **k: io.BytesIO(json.dumps(payload).encode())) as call:
                with redirect_stdout(io.StringIO()):
                    run_graphics(output, 'stills')
                    run_graphics(output, 'stills')
            self.assertEqual(call.call_count, 2)
            row = json.loads((output / 'token_usage.json').read_text())['graphics']
            self.assertEqual((row['input_tokens'], row['output_tokens'], row['requests']), (240, 60, 2))
