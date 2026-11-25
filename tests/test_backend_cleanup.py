"""CPU-only tests: SAM3 must not import GUI PyTorch just to clear SAM2."""
import builtins
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PIL import Image
from sam_backends import Sam2Local
from roi_utils import FULL, CROP, run_scoped


class BackendCleanupTests(unittest.TestCase):
    def test_cold_clear_does_not_import_torch(self):
        real_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name == 'torch' or name.startswith('torch.'):
                raise OSError('Simulated WinError 1114')
            return real_import(name, *args, **kwargs)
        with patch.dict(sys.modules, {}), patch('builtins.__import__', side_effect=guarded):
            sys.modules.pop('torch', None)
            backend = Sam2Local()
            for scope in (FULL, CROP):
                with self.subTest(scope=scope):
                    worker = Mock(side_effect=lambda path, prompt, threshold: Image.new('L', (32, 32) if scope == FULL else (16, 16), 255))
                    result = run_scoped('SAM3 text', Image.new('RGB', (32, 32)), Path('sample.png'), [], 'flames', .4, scope, (8, 8, 24, 24), backend, worker, None)
                    worker.assert_called_once()
                    self.assertEqual(result.getbbox(), (0, 0, 32, 32) if scope == FULL else (8, 8, 24, 24))
                    self.assertNotIn('torch', sys.modules)

    def test_initialized_cuda_cache_released(self):
        cuda = Mock()
        cuda.is_initialized.return_value = True
        backend = Sam2Local()
        backend.predictor = object()
        backend.loaded_model = 'SAM2.1 small'
        backend.image_key = 'image'
        with patch.dict(sys.modules, {'torch': SimpleNamespace(cuda=cuda)}):
            backend.clear()
        self.assertIsNone(backend.predictor)
        self.assertIsNone(backend.loaded_model)
        self.assertIsNone(backend.image_key)
        cuda.empty_cache.assert_called_once_with()
        cuda.is_available.assert_not_called()

    def test_uninitialized_cuda_not_touched(self):
        cuda = Mock()
        cuda.is_initialized.return_value = False
        with patch.dict(sys.modules, {'torch': SimpleNamespace(cuda=cuda)}):
            Sam2Local().clear()
        cuda.empty_cache.assert_not_called()
        cuda.is_available.assert_not_called()

    def test_partial_module_without_cuda(self):
        with patch.dict(sys.modules, {'torch': SimpleNamespace()}):
            Sam2Local().clear()


if __name__ == '__main__':
    unittest.main()
