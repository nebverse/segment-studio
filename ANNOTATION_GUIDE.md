# Annotation guide

[← Home](README.md) · [Installation](INSTALLATION.md) · [Models](models/README.md)

## 1. What to label

Visible flames in RGB only. Exclude smoke, vegetation, reflections, burnt ground and flames entirely hidden by smoke. IR is an optional inspection aid, not a registered mask source. Every prediction needs human review.

## 2. Workspace at a glance

| Area | Controls |
| :--- | :--- |
| Top toolbar | Open RGB folder, optional IR folder, previous/next image |
| Segment | Model, full image/ROI/box, context, prompts, Run/Apply/Discard |
| Edit | Paint fire, Erase, SAM positive/negative, Polygon add/erase, Edit boundary, Draw ROI, Pan |
| View | Overlay colour/opacity, cyan boundary, candidate preview, Fit image, Fit ROI, read-only IR |
| Save controls | Annotator, Save draft, Approve + save |

| Overlay | Meaning |
| :--- | :--- |
| Purple (default) | Accepted working mask |
| Green | Temporary pending model candidate |
| Amber rectangle | Selected ROI |
| Blue rectangle | Extra crop context |
| Yellow nodes | Editable polygon vertices |

## 3. Full-image segmentation

1. Open RGB folder; existing saved masks reopen automatically.
2. In Segment, choose SAM3 text with prompt `flames`, or select SAM2.1 and place at least one positive click on flame (negative clicks mark background). The Colour demo is a simple RGB heuristic.
3. Select Full image and Run candidate.
4. Inspect the green result. Choose Add (union) and Apply candidate to accept it; Discard to reject it.

## 4. Recover missed flames with an ROI

**Works with SAM3, every SAM2.1 variant and the colour filter.**

1. Choose ROI crop and click Draw ROI (Ctrl+R). Drag around a missed flame; minimum rectangle size is 8 × 8 original image pixels.
2. Optionally Fit ROI. Choose context (0–50%, default 10% extra per side). Context helps the model see surroundings, but changes are restricted to the original rectangle.
3. SAM3: keep or adjust the text prompt; SAM2.1: rectangle alone is sufficient, optional positive/negative clicks inside refine it; colour filter: no prompts.
4. Run candidate, inspect and apply with Add (union).
5. Repeat for more ROIs or switch models. Clear ROI returns to Full image without clearing the working mask or pending candidate.

The alternative SAM2 box prompt mode uses full-image embedding and a native geometric prompt rather than cropping. It is only available for SAM2.1. See [models](models/README.md) for the difference.

## 5. Candidate handling and merging

| Apply as | Effect |
| :--- | :--- |
| Add (union) | Keep old mask and add new pixels |
| Replace | Replace mask in candidate's original inference area |
| Subtract | Remove candidate pixels |
| Intersect | Keep shared pixels in candidate's original inference area |

All four operations preserve pixels outside the candidate's captured ROI. Full-image Replace/Intersect affect the whole mask; empty destructive candidates require confirmation.

If another prediction is pending, switching scope/model/rectangle retains it. When running again: Yes applies the previous prediction using the selected merge operation, No discards and runs, Cancel keeps it and stops. When saving: Yes applies and saves, No cancels; explicitly discard first to save without it. Hiding a green preview does not discard it.

## 6. Manual and polygon editing

- Paint fire / Erase: brush radius/size control is in original image pixels.
- Polygon add / Polygon erase: place points, Finish polygon or Enter.
- Edit boundary: apply the candidate first, select the tool and click a connected masked flame region.

| Vertex action | How to use |
| :--- | :--- |
| Move | Drag a yellow vertex |
| Add | Click near a polygon edge (or Shift-click) |
| Remove | Click a vertex, or select one then Delete selected |
| Undo vertex | Revert individual temporary changes |
| Commit boundary | Apply the local rasterized boundary difference |
| Cancel edit | Discard temporary polygon changes |

At least three vertices must remain. The editable polygon is simplified, not an exact raster trace. Local boundary correction preserves unaffected details, holes and unrelated components as far as the edit permits. Avoid self-crossing polygons; inspect at high zoom and use the brush for fine tips or holes. Undo after commit restores the previous working mask.

## 7. Saving and reopening

Save draft during revision and Approve + save after review. Navigation/closing warns about pending or unsaved work. New output is inside the selected RGB folder:

```text
segment_studio_output/
  masks/                 # single-channel PNG, 0 background / 255 flame
  overlays/              # JPEG inspection previews
  metadata/              # JSON per image
  annotation_manifest.csv
```

Saved masks are checked first, then legacy firemask_output/masks, input_masks, masks, or matching image stem + _mask.png. Import single-channel 0/1 or 0/255 masks at exact RGB dimensions. Raw photos and source masks are not modified. Never train using overlays; retain annotation status and use independent fire-event splits to avoid leakage.

## 8. Optional infrared preview

Choose IR folder (optional) and View IR only. For explicit pairing, place image_pairs.csv in the RGB folder:

```csv
rgb_file,ir_file
photo_001.jpg,photo_001_ir.jpg
```

See [example CSV](image_pairs_example.csv). Filenames can also be matched automatically; matching does not prove registration. IR view is inspection-only; return to RGB to edit. Output stays in RGB coordinates.

## 9. Shortcuts

| Shortcut | Action |
| :--- | :--- |
| Mouse wheel | Zoom around pointer |
| Right-button drag | Pan |
| Ctrl+R | Draw ROI |
| Ctrl+Z | Undo vertex while editing; otherwise undo mask |
| Ctrl+S | Save draft |
| Enter | Finish polygon or commit boundary |
| Escape | Cancel temporary shape |
| Shift-click near edge | Add vertex |
| Delete | Remove selected vertex |

[Problems? See Troubleshooting →](TROUBLESHOOTING.md)
