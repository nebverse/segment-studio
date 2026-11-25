"""CPU-only ROI regression tests. Run with python -m unittest discover -s tests -p test_roi.py."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from PIL import Image

from roi_utils import FULL,CROP,BOX,make_roi,padded_roi,scoped_points,run_scoped,merge_scoped
from mask_utils import colour_candidate,merge_masks

class ROITests(unittest.TestCase):
    def setUp(self):
        self.image=Image.new('RGB',(60,40),(255,80,0))
        self.path=Path('sample.jpg')
        self.roi=(10,5,30,25)
        self.sam=Mock()
        self.sam.predict.side_effect=lambda variant,image,points,key,**kwargs: Image.new('L',image.size,255)
        self.sam3=Mock(return_value=Image.new('L',(20,20),255))

    def run_scope(self,variant,scope,points=(),roi=None):
        return run_scoped(variant,self.image,self.path,list(points),'flames',.4,scope,
                          self.roi if roi is None else roi,self.sam,self.sam3,colour_candidate)

    def check_mask(self,m):
        self.assertEqual(m.size,self.image.size)
        self.assertEqual(m.getbbox(),self.roi)
        self.assertEqual(set(m.getdata()),{0,255})

    def test_roi_reverse_clip_and_small(self):
        self.assertEqual(make_roi((29,24),(10,5),self.image.size),self.roi)
        self.assertEqual(make_roi((0,0),(100,100),self.image.size),(0,0,60,40))
        self.assertIsNone(make_roi((3,3),(7,7),self.image.size))

    def test_colour_full_and_crop(self):
        self.check_mask(self.run_scope('Colour demo (not AI)',CROP))
        self.assertEqual(self.run_scope('Colour demo (not AI)',FULL).getbbox(),(0,0,60,40))

    def test_crop_sam2_translates_and_caches(self):
        points=[(11,6,1),(29,24,0),(30,24,1),(2,2,0)]
        self.check_mask(self.run_scope('SAM2.1 small',CROP,points))
        variant,img,pts,key=self.sam.predict.call_args.args
        self.assertEqual(img.size,(20,20))
        self.assertEqual(pts,[(1,1,1),(19,19,0)])
        self.run_scope('SAM2.1 small',CROP,points)
        self.assertEqual(key,self.sam.predict.call_args.args[3])
        self.run_scope('SAM2.1 small',CROP,points,roi=(8,4,30,25))
        self.assertNotEqual(key,self.sam.predict.call_args.args[3])
        self.check_mask(self.run_scope('SAM2.1 small',CROP,[(0,0,1)]))
        self.assertEqual(self.sam.predict.call_args.args[2],[])
        self.assertEqual(self.sam.predict.call_args.kwargs['box'],(0,0,19,19))
        with self.assertRaises(ValueError): self.run_scope('SAM2.1 small',FULL,[])

    def test_native_box_no_clicks_and_clipped(self):
        self.check_mask(self.run_scope('SAM2.1 large',BOX))
        self.assertEqual(self.sam.predict.call_args.args[1].size,self.image.size)
        self.assertEqual(self.sam.predict.call_args.args[2],[])
        self.assertEqual(self.sam.predict.call_args.kwargs['box'],(10,5,29,24))
        key=self.sam.predict.call_args.args[3]
        self.run_scope('SAM2.1 large',FULL,[(10,5,1)])
        self.assertEqual(key,self.sam.predict.call_args.args[3])
        with self.assertRaises(ValueError): self.run_scope('SAM3 text',BOX)

    def test_sam3_lossless_crop_and_cleanup(self):
        seen=[]
        def worker(path,prompt,threshold):
            seen.append(path)
            self.assertEqual(prompt,'flames')
            self.assertEqual(threshold,.4)
            with Image.open(path) as im:
                self.assertEqual(im.size,(20,20))
                self.assertEqual(im.getpixel((0,0)),(255,80,0))
            return Image.new('L',(20,20),255)
        self.sam3.side_effect=worker
        self.check_mask(self.run_scope('SAM3 text',CROP))
        self.sam.clear.assert_called_once()
        self.assertFalse(seen[0].exists())

    def test_merge_all_modes_preserve_outside(self):
        base=Image.new('L',self.image.size,0)
        base.putpixel((1,1),255); base.putpixel((12,12),255)
        cand=Image.new('L',self.image.size,0)
        cand.putpixel((13,13),255); cand.putpixel((55,35),255)
        expected={'Replace':(0,255),'Add (union)':(255,255),'Subtract':(255,0),'Intersect':(0,0)}
        for mode,pixels in expected.items():
            with self.subTest(mode=mode):
                out=merge_scoped(base,cand,mode,self.roi,merge_masks)
                self.assertEqual(out.getpixel((1,1)),255)
                self.assertEqual(out.getpixel((55,35)),0)
                self.assertEqual((out.getpixel((12,12)),out.getpixel((13,13))),pixels)
                self.assertEqual(base.getpixel((12,12)),255)

    def test_padded_crop_and_box(self):
        self.assertEqual(padded_roi(self.roi,self.image.size,10),(8,3,32,27))
        self.assertEqual(padded_roi((0,0,20,20),self.image.size,50),(0,0,30,30))
        args=('SAM2.1 small',self.image,self.path,[(12,8,1),(8,3,0)],'flames',.4,CROP,self.roi,self.sam,self.sam3,colour_candidate)
        out=run_scoped(*args,context_percent=10)
        self.check_mask(out)
        self.assertEqual(self.sam.predict.call_args.args[1].size,(24,24))
        self.assertEqual(self.sam.predict.call_args.args[2],[(4,5,1)])
        self.assertEqual(self.sam.predict.call_args.kwargs['box'],(2,2,21,21))
        k=self.sam.predict.call_args.args[3]
        run_scoped(*args,context_percent=20)
        self.assertNotEqual(k,self.sam.predict.call_args.args[3])

    def test_padded_sam3_crops_back(self):
        def worker(path,prompt,threshold):
            with Image.open(path) as im:
                self.assertEqual(im.size,(24,24))
            return Image.new('L',(24,24),255)
        self.sam3.side_effect=worker
        self.check_mask(run_scoped('SAM3 text',self.image,self.path,[],'flames',.4,CROP,self.roi,self.sam,self.sam3,colour_candidate,context_percent=10))

    def test_wrong_shape_rejected(self):
        self.sam3.return_value=Image.new('L',(3,3),255)
        with self.assertRaises(ValueError): self.run_scope('SAM3 text',CROP)

if __name__=='__main__': unittest.main(verbosity=2)
