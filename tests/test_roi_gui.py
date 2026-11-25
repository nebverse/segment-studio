"""Desktop smoke test (synthetic image, no model weights, no network)."""
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from segment_studio import FireAnnotator
from roi_utils import FULL,CROP,BOX

def main():
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp)
        for name in ('a.png','b.png'):
            Image.new('RGB',(240,180),(255,80,0)).save(folder/name)
        gui=FireAnnotator()
        try:
            gui.update(); gui.folder=folder; gui.images=sorted(folder.glob('*.png')); gui.open_index(0); gui.update()
            # Verify original pixel geometry at nonunit zoom + offset.
            gui.scaling=1.7; gui.offset=(41,19)
            def event(x,y):
                a,b=gui.to_screen((x,y)); return SimpleNamespace(x=round(a),y=round(b),state=0)
            gui.start_roi(); gui.left_down(event(109,89)); gui.left_drag(event(40,30)); gui.left_up(event(40,30)); gui.update()
            assert gui.roi==(40,30,110,90),gui.roi
            assert gui.scope.get()==CROP
            assert str(gui.context_box.cget('state'))=='readonly'
            gui.fit_roi(); gui.update(); assert gui.scaling>1.7
            gui.scope.set(BOX); gui._scope_changed(); assert str(gui.context_box.cget('state'))=='disabled'
            gui.model.set('Colour demo (not AI)'); assert gui.scope.get()==CROP
            gui.mask.putpixel((5,5),255)
            gui.model.set('Colour demo (not AI)'); gui.run_candidate()
            end=time.monotonic()+10
            while gui.busy and time.monotonic()<end:
                gui.update(); time.sleep(.02)
            assert not gui.busy and gui.pending_candidate is not None
            assert gui.pending_candidate.getbbox()==gui.roi
            assert gui.mask.getpixel((50,50))==0
            gui.merge.set('Replace'); gui.apply_candidate(); gui.update()
            assert gui.mask.getpixel((5,5))==255 and gui.mask.getpixel((50,50))==255
            gui.undo(); assert gui.mask.getpixel((5,5))==255 and gui.mask.getpixel((50,50))==0
            gui.save('draft'); assert gui._mask_path(gui.image_path).exists()
            gui.open_index(1); gui.update(); assert gui.roi is None and gui.scope.get()==FULL
            gui.start_roi(); gui.left_down(event(10,10)); gui.left_drag(event(30,30)); gui.cancel_edit(); gui.left_up(event(30,30)); assert gui.roi is None
            gui.clear_roi(); assert gui.scope.get()==FULL
            # Empty candidate Replace must explicitly confirm before touching working mask.
            from unittest.mock import patch
            gui.mask.putpixel((7,7),255); gui.pending_candidate=Image.new('L',gui.image.size,0); gui.pending_model='empty'; gui.merge.set('Replace')
            with patch('segment_studio.messagebox.askyesno',return_value=False): gui.apply_candidate()
            assert gui.mask.getpixel((7,7))==255
            with patch('segment_studio.messagebox.askyesno',return_value=True): gui.apply_candidate()
            assert gui.mask.getpixel((7,7))==0
        finally: gui.destroy()
    print('GUI ROI smoke test PASS: reverse drag, zoom coordinates, threaded preview, scoped replace, undo, save, navigation reset, cancel')

if __name__ == '__main__':
    main()
