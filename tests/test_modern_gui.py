"""Real Tkinter vertex controls and transactional edit tests; no SAM weights."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageDraw
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from segment_studio import FireAnnotator
from unittest.mock import patch


def main():
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp); Image.new('RGB',(320,240),(75,75,75)).save(folder/'sample.png')
        gui=FireAnnotator()
        try:
            gui.geometry('920x680'); gui.update(); gui.folder=folder; gui.images=[folder/'sample.png']; gui.open_index(0); gui.update()
            gui.mask=Image.new('L',(320,240)); d=ImageDraw.Draw(gui.mask); d.rectangle((40,40,140,140),fill=255); d.rectangle((210,160,250,190),fill=255)
            original=gui.mask.tobytes(); gui.scaling=1.5; gui.offset=(20,20)
            def ev(p,state=0):
                x,y=gui.to_screen(p); return SimpleNamespace(x=round(x),y=round(y),state=state)
            gui._set_tool('Edit boundary'); gui.left_down(ev((80,80))); gui.update()
            assert len(gui.edit_contour)==4
            assert gui.tabs.select()==str(gui.edit_tab)
            a,b=gui.edit_contour[:2]; mid=tuple((x+y)//2 for x,y in zip(a,b))
            gui.vertex_action.set('Add'); gui.left_down(ev(mid)); assert len(gui.edit_contour)==5
            assert gui.mask.tobytes()==original
            added=gui.edit_contour[gui.selected_vertex]; gui.vertex_action.set('Move'); gui.left_down(ev(added));
            target=(added[0]-15,added[1]-15); gui.left_drag(ev(target)); gui.left_up(ev(target)); assert target in gui.edit_contour
            gui.undo_vertex(); assert added in gui.edit_contour and target not in gui.edit_contour
            gui.vertex_action.set('Remove'); gui.left_down(ev(added)); assert len(gui.edit_contour)==4
            gui.undo_vertex(); assert len(gui.edit_contour)==5
            gui.undo_vertex(); assert len(gui.edit_contour)==4
            assert gui.mask.tobytes()==original
            # Closing edge insertion and Delete button semantics.
            a,b=gui.edit_contour[-1],gui.edit_contour[0]; mid=tuple((x+y)//2 for x,y in zip(a,b))
            gui.left_down(ev(mid,1)); assert len(gui.edit_contour)==5
            gui.remove_nearest_vertex(); assert len(gui.edit_contour)==4
            gui.mode.set('Paint fire'); assert gui.mode.get()=='Edit boundary'
            gui.clear_mask(); assert gui.mask.tobytes()==original
            gui.commit_boundary(); assert gui.mask.tobytes()==original and not gui.undo_stack
            gui.select_contour((80,80)); a,b=gui.edit_contour[:2]; mid=tuple((x+y)//2 for x,y in zip(a,b))
            gui.vertex_action.set('Add'); gui.left_down(ev(mid)); added=gui.edit_contour[gui.selected_vertex]
            gui.vertex_action.set('Move'); gui.left_down(ev(added)); target=(added[0]-15,added[1]-15); gui.left_drag(ev(target)); gui.left_up(ev(target)); gui.commit_boundary()
            assert gui.mask.tobytes()!=original and gui.mask.getpixel((220,170))==255
            gui.undo(); assert gui.mask.tobytes()==original
            gui.select_contour((80,80)); gui.vertex_action.set('Remove'); gui.left_down(ev(gui.edit_contour[0])); assert len(gui.edit_contour)==3
            gui.left_down(ev(gui.edit_contour[0])); assert len(gui.edit_contour)==3
            gui.cancel_edit(); assert gui.mask.tobytes()==original
            # Each tab is accessible and image workspace remains visible at min size.
            for tab in (gui.segment_tab,gui.edit_tab,gui.view_tab):
                gui.tabs.select(tab); gui.update(); assert gui.canvas.winfo_width()>450 and gui.canvas.winfo_height()>350
            gui.model.set('SAM3 text'); gui.tabs.select(gui.segment_tab); gui.update(); assert gui.sam3_options.winfo_ismapped()
            gui.model.set('SAM2.1 small'); gui.update(); assert gui.sam2_options.winfo_ismapped() and not gui.sam3_options.winfo_ismapped()
        finally: gui.destroy()
    print('Modern GUI test PASS: add/move/remove, closing edge, vertex undo, no-op, guards, commit, mask undo, tabs and model controls')

if __name__ == '__main__':
    main()
