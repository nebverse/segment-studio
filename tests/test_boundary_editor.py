import unittest
from PIL import Image, ImageDraw
from mask_utils import apply_boundary_delta, detect_component_polygon

class BoundaryDeltaTests(unittest.TestCase):
    def setUp(self):
        self.mask=Image.new('L',(100,100)); d=ImageDraw.Draw(self.mask)
        d.rectangle((10,10,60,60),fill=255); d.rectangle((25,25,40,40),fill=0)
        d.rectangle((30,30,33,33),fill=255); d.rectangle((80,80,90,90),fill=255)
        # Small protrusion should not disappear on unchanged edge.
        d.rectangle((60,45,62,48),fill=255)
        self.simple,self.full=detect_component_polygon(self.mask,(15,15),10,simplify_px=4,return_full=True)
    def test_noop(self):
        self.assertEqual(apply_boundary_delta(self.mask,self.full,self.simple,self.simple).tobytes(),self.mask.tobytes())
    def test_contract_preserves_island_and_other_component(self):
        base=[(10,10),(10,60),(60,60),(60,10)]
        edit=[(10,10),(10,24),(60,24),(60,10)]
        out=apply_boundary_delta(self.mask,self.full,base,edit)
        self.assertEqual(out.getpixel((30,30)),255)
        self.assertEqual(out.getpixel((85,85)),255)
        self.assertEqual(out.getpixel((15,50)),0)
        self.assertEqual(out.getpixel((15,15)),255)
    def test_expand_preserves_hole_and_unedited_detail(self):
        base=[(10,10),(10,60),(60,60),(60,10)]
        edit=[(5,10),(10,60),(60,60),(60,10)]
        out=apply_boundary_delta(self.mask,self.full,base,edit)
        self.assertEqual(out.getpixel((7,10)),255)
        self.assertEqual(out.getpixel((27,27)),0)
        self.assertEqual(out.getpixel((62,46)),255)
        self.assertEqual(out.getpixel((85,85)),255)
        self.assertEqual(self.mask.getpixel((7,10)),0)

if __name__=='__main__': unittest.main()
