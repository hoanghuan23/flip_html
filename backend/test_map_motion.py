"""Regression checks for generated map timelines, independent of network tiles."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from map_renderer import _write_pages


class MapMotionTests(unittest.TestCase):
    def test_camera_braking_and_scene_handoffs(self):
        plan = {
            'stops': [{'name': name, 'coord': coord} for name, coord in
                      [('A', [105, 21]), ('B', [108, 16]), ('C', [109, 12])]],
            'legs': [{'coordinates': [[105, 21], [106, 19], [108, 16]]},
                     {'coordinates': [[108, 16], [109, 14], [109, 12]]}],
            'phases': [{'mode': 'depart', 'stopIndex': 0},
                       {'mode': 'move', 'stopIndex': 1, 'legIndex': 0},
                       {'mode': 'stop', 'stopIndex': 1},
                       {'mode': 'move', 'stopIndex': 2, 'legIndex': 1},
                       {'mode': 'stop', 'stopIndex': 2},
                       {'mode': 'summary', 'stopIndex': 2}],
            'styleUrl': 'https://tiles.openfreemap.org/styles/liberty',
            'attribution': 'OpenFreeMap',
        }
        script = {'title': 'Camera regression', 'phases': [
            {'id': index, 'name': f'Phase {index}', 'duration': duration}
            for index, duration in enumerate([21.6, 13.1667, 20.9667, 9.8667, 19.2, 13.8], 1)]}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            _write_pages(script, output, plan, 'test-revision')
            helper = Path(__file__).resolve().parent.parent / 'frontend/scripts/map-motion-test.cjs'
            result = subprocess.run(['node', str(helper), str(output)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
