"""Regression for full-image -> ROI accumulation, save and explicit discard."""
import tempfile,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image, ImageDraw
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from segment_studio import FireAnnotator
from roi_utils import FULL,CROP


def main():
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp)
        image=Image.new('RGB',(240,180),(30,30,30))
        ImageDraw.Draw(image).rectangle((120,90,145,115), fill=(255,80,0))
        image.save(folder/'a.png')
        gui=FireAnnotator()
        try:
            gui.update(); gui.folder=folder; gui.images=[folder/'a.png']; gui.open_index(0); gui.update()
            def seed(box,scope=FULL,roi=None):
                gui.pending_candidate=Image.new('L',image.size,0)
                ImageDraw.Draw(gui.pending_candidate).rectangle(box,fill=255)
                gui.pending_model='SAM3 text'; gui.pending_scope=scope; gui.pending_roi=roi
            seed((10,10,30,30))
            first=gui.pending_candidate
            gui.scope.set(CROP); gui._scope_changed()
            gui.start_roi(); gui.scaling=1; gui.offset=(0,0)
            def ev(x,y): return SimpleNamespace(x=x,y=y,state=0)
            gui.left_down(ev(110,80)); gui.left_drag(ev(155,125)); gui.left_up(ev(155,125))
            gui.context_percent.set('20'); gui._context_changed()
            gui.model.set('Colour demo (not AI)')
            assert gui.pending_candidate is first and gui.pending_roi is None
            assert gui.mask.getbbox() is None
            with patch('segment_studio.messagebox.askyesnocancel',return_value=None): gui.run_candidate()
            assert not gui.busy and gui.pending_candidate is first
            with patch('segment_studio.messagebox.askyesnocancel',return_value=True): gui.run_candidate()
            end=time.monotonic()+10
            while gui.busy and time.monotonic()<end:
                gui.update(); time.sleep(.02)
            assert not gui.busy and gui.pending_candidate is not None
            assert gui.mask.getpixel((20,20))==255 and gui.mask.getpixel((130,100))==0
            assert gui.pending_candidate.getpixel((130,100))==255
            # Changing settings cannot change the original candidate's captured ROI.
            captured=gui.pending_roi; gui.clear_roi(); assert gui.pending_roi==captured
            with patch('segment_studio.messagebox.askyesno',return_value=False): gui.save('draft')
            assert gui.pending_candidate is not None and not gui._mask_path(gui.image_path).exists()
            with patch('segment_studio.messagebox.askyesno',return_value=True): gui.save('draft')
            with Image.open(gui._mask_path(gui.image_path)) as saved:
                assert saved.getpixel((20,20))==255 and saved.getpixel((130,100))==255
            assert gui.pending_candidate is None
            gui.open_index(0); assert gui.mask.getpixel((20,20))==255 and gui.mask.getpixel((130,100))==255
            # Scoped Replace uses captured region, not newly selected scope.
            seed((130,100,135,105),CROP,(110,80,156,126)); gui.merge.set('Replace')
            gui.apply_candidate(); assert gui.mask.getpixel((20,20))==255 and gui.mask.getpixel((120,90))==0
            gui.undo(); assert gui.mask.getpixel((120,90))==255
            # Discard is explicit, and does not change accepted mask.
            seed((50,50,60,60)); gui.discard_candidate(); assert gui.mask.getpixel((55,55))==0
            # Empty destructive candidate cancellation blocks save/new inference.
            gui.pending_candidate=Image.new('L',image.size,0); gui.pending_model='empty'
            with patch('segment_studio.messagebox.askyesno',side_effect=[True,False]): gui.save('approved')
            assert gui.pending_candidate is not None and gui.mask.getpixel((20,20))==255
            with patch('segment_studio.messagebox.askyesno',return_value=False): assert not gui._can_abandon()
        finally: gui.destroy()
    print('Candidate workflow regression PASS')

if __name__ == '__main__':
    main()
