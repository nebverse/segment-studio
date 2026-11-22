"""Optional GUI smoke test. Requires a desktop/Xvfb and no SAM installations."""
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from segment_studio import FireAnnotator

with tempfile.TemporaryDirectory() as t:
    folder=Path(t)
    image=Image.new('RGB',(1200,900),(70,70,75))
    d=ImageDraw.Draw(image)
    d.polygon([(550,600),(570,280),(600,520),(620,200),(650,580),(710,650)],fill=(255,120,25))
    image.save(folder/'sample_rgb.jpg')
    gui=FireAnnotator()
    gui.update()
    gui.folder=folder
    gui.images=[folder/'sample_rgb.jpg']
    gui.open_index(0)
    gui.update()
    gui.pending_candidate=Image.new('L',image.size,0)
    ImageDraw.Draw(gui.pending_candidate).ellipse((500,200,710,650),fill=255)
    gui.pending_model='synthetic candidate'
    gui.apply_candidate()
    gui.update()
    assert gui.mask.getpixel((600,350)) == 255
    gui.save('draft')
    assert (folder/'firemask_output/masks/sample_rgb.png').exists()
    gui.mask=Image.new('L',image.size,0)
    gui.open_index(0)
    assert gui.mask.getpixel((600,350)) == 255
    gui.mode.set('Edit boundary')
    gui.select_contour((600,350))
    assert gui.edit_contour is not None
    old=gui.edit_contour[0]
    gui.edit_contour[0]=(old[0]+10,old[1])
    gui.commit_boundary()
    gui.undo()
    gui.update()
    gui.destroy()
print('GUI smoke test PASS: open, candidate apply, save/reload, contour commit, undo')
