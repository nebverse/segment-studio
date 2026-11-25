"""Portable model path precedence and legacy annotation compatibility."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import sam_backends

class PortabilityTests(unittest.TestCase):
    def test_mixed_checkpoint_folders(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            local = root / 'models' / 'sam2.1'
            external = root / 'external_weights'
            local.mkdir(parents=True)
            external.mkdir()
            small = 'sam2.1_hiera_small.pt'
            large = 'sam2.1_hiera_large.pt'
            (local / small).touch()
            (external / small).touch()
            (external / large).touch()
            with patch.object(sam_backends, 'ROOT', root), patch.object(sam_backends, '_local_config', return_value={'sam2_models': str(external)}), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(sam_backends.sam2_checkpoint('SAM2.1 small'), local / small)
                self.assertEqual(sam_backends.sam2_checkpoint('SAM2.1 large'), external / large)
                with patch.dict(os.environ, {'SEGMENT_STUDIO_SAM2_MODELS': str(external)}):
                    self.assertEqual(sam_backends.sam2_checkpoint('SAM2.1 small'), external / small)

    def test_legacy_mask_source_order(self):
        from segment_studio import FireAnnotator
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as t:
            folder = Path(t)
            image = folder / 'example.jpg'
            stub = SimpleNamespace(folder=folder, _out=lambda: folder / 'segment_studio_output')
            stub._mask_path = lambda p: FireAnnotator._mask_path(stub, p)
            sources = FireAnnotator._sources(stub, image)
            self.assertEqual(sources[0], folder / 'segment_studio_output/masks/example.png')
            self.assertEqual(sources[1], folder / 'firemask_output/masks/example.png')

if __name__ == '__main__':
    unittest.main()
