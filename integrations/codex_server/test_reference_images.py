"""Run after applying reference_images.patch to the companion codex_server."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch

from httpx import ASGITransport, AsyncClient

SERVER_ROOT = Path(__file__).resolve().parents[3] / 'codex_server'
SOURCE = Path(os.environ.get('CODEX_SERVER_SOURCE', SERVER_ROOT / 'server.py'))


class ReferenceImagesApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.is_file():
            raise unittest.SkipTest('Companion codex_server is not installed.')
        sys.path.insert(0, str(SERVER_ROOT))
        try:
            spec = importlib.util.spec_from_file_location('reference_api_test', SOURCE)
            cls.server = importlib.util.module_from_spec(spec)
            with patch.dict(os.environ, {'CODEX_API_TOKEN': 'test-token'}):
                spec.loader.exec_module(cls.server)
        finally:
            sys.path.remove(str(SERVER_ROOT))

    async def asyncSetUp(self):
        self.server.API_TOKEN = 'test-token'
        self.client = AsyncClient(transport=ASGITransport(app=self.server.app), base_url='http://test')
        self.addAsyncCleanup(self.client.aclose)
        self.png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8'
                                    '/x8AAwMCAO+aElkAAAAASUVORK5CYII=')

    async def post(self, references, headers=None):
        return await self.client.post('/generate-image', json={
            'prompt': 'Xeko pointing', 'model': 'test', 'reference_images': references},
            headers={'x-api-key': 'test-token'} if headers is None else headers)

    async def test_attached_bytes_reach_cli_and_tool_prompt_then_are_cleaned(self):
        process = Mock(returncode=0)
        process.communicate = AsyncMock(return_value=(b'', b''))
        directories = []

        async def execute(*args, **kwargs):
            directory = Path(kwargs['cwd'])
            directories.append(directory)
            indices = [i for i, arg in enumerate(args) if arg == '--image']
            self.assertEqual(len(indices), 2)
            for index in indices:
                self.assertEqual(Path(args[index + 1]).read_bytes(), self.png)
            (directory / 'output.png').write_bytes(self.png)
            return process

        with patch.object(self.server.asyncio, 'create_subprocess_exec', side_effect=execute), \
                patch.object(self.server, 'resolve_codex_executable', return_value='codex-test'):
            response = await self.post(['data:image/png;base64,' + base64.b64encode(self.png).decode()] * 2)
        self.assertEqual(response.status_code, 200, response.text)
        prompt = process.communicate.call_args.kwargs['input'].decode()
        self.assertIn('referenced_image_paths', prompt)
        self.assertIn('canonical character identity', prompt)
        self.assertFalse(directories[0].exists())

    async def test_invalid_references_and_unauthorized_requests_do_not_start_cli(self):
        png = 'data:image/png;base64,' + base64.b64encode(self.png).decode()
        with patch.object(self.server.asyncio, 'create_subprocess_exec') as execute:
            for references in ([png] * 5, ['https://example.com/file.png'],
                               ['data:image/png;base64,bad!'], ['data:image/png;base64,YmFk']):
                response = await self.post(references)
                self.assertEqual(response.status_code, 422, response.text)
            response = await self.post([png], headers={})
            self.assertEqual(response.status_code, 401)
            execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
