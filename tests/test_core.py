"""Regression tests for annotation semantics. Run: python -m unittest discover -s tests -v"""
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from mask_utils import (binary_mask, colour_candidate, merge_masks, mask_pack, mask_unpack,
                        detect_component_polygon, replace_polygon_component, save_png_atomic,
                        write_manifest, load_image_pairs)


class CoreTests(unittest.TestCase):
    def test_merge(self):
        a = Image.new('L',(10,10),0)
        b = Image.new('L',(10,10),0)
        a.putpixel((1,1),255)
        b.putpixel((2,2),255)
        self.assertEqual(int(np.asarray(merge_masks(a,b,'Add (union)')).sum()),510)
        self.assertEqual(int(np.asarray(merge_masks(a,b,'Replace')).sum()),255)
        self.assertEqual(int(np.asarray(merge_masks(a,b,'Subtract')).sum()),255)
        self.assertEqual(int(np.asarray(merge_masks(a,b,'Intersect')).sum()),0)

    def test_undo_pack(self):
        a=Image.new('L',(700,400),0)
        ImageDraw.Draw(a).ellipse((10,20,160,190),fill=255)
        self.assertTrue(np.array_equal(np.asarray(a),np.asarray(mask_unpack(mask_pack(a)))))

    def test_select_and_commit_boundary(self):
        a=Image.new('L',(200,200),0)
        dr=ImageDraw.Draw(a)
        dr.ellipse((50,50,130,130),fill=255)
        dr.ellipse((75,75,95,95),fill=0) # hole survives deformation
        found=detect_component_polygon(a,(110,110),20,return_full=True)
        self.assertIsNotNone(found)
        simple, raw=found
        edited=[(x+5,y) for x,y in simple]
        b=replace_polygon_component(a,raw,edited)
        self.assertEqual(b.getpixel((85,85)),0)
        self.assertTrue(np.asarray(b).sum()>0)
        self.assertEqual(a.getpixel((85,85)),0)

    def test_masks_do_not_guess_rgb_overlays(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            rgb=Image.new('RGB',(20,30),(255,50,20))
            rgb.save(folder/'overlay.png')
            with self.assertRaises(ValueError):
                binary_mask(folder/'overlay.png',(20,30))
            m=Image.new('L',(20,30),0)
            m.putpixel((4,4),1)
            save_png_atomic(m,folder/'mask.png')
            loaded=binary_mask(folder/'mask.png',(20,30))
            self.assertEqual(loaded.getpixel((4,4)),255)
            self.assertEqual(colour_candidate(rgb).size,rgb.size)

    def test_pairs(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'image_pairs.csv'
            path.write_text('rgb_file,ir_file\nA_rgb.jpg,A_ir.jpg\n',encoding='utf-8')
            self.assertEqual(load_image_pairs(path),{'A_rgb.jpg':'A_ir.jpg'})


    def test_find_checkpoint_in_reused_folder(self):
        from unittest.mock import patch
        from sam_backends import sam2_checkpoint
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            empty = root / 'repo_models'
            legacy = root / 'existing_models'
            empty.mkdir()
            legacy.mkdir()
            existing = legacy / 'sam2.1_hiera_small.pt'
            existing.write_bytes(b'example-only')
            with patch('sam_backends._sam2_locations', return_value=[empty, legacy]):
                self.assertEqual(sam2_checkpoint('SAM2.1 small'), existing)


if __name__=='__main__':
    unittest.main()
