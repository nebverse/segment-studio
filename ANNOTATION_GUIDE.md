# Annotation policy and controls

**Target:** visible RGB flames only. Exclude smoke, vegetation, reflections, burnt ground and flames fully hidden by smoke. IR is inspection-only; it does not establish RGB–IR registration or generate thermal masks. Raw photographs and source masks remain unchanged; approved and draft binary masks are saved separately to `segment_studio_output/`.

## 1. Full-image baseline and small-flame refinement

1. Open RGB folder. Saved masks reopen automatically; review before changing them.
2. In Segment, choose `SAM3 text`, prompt `flames`, and Full image. Alternatively select a SAM2.1 variant and add positive/negative clicks. The colour demo is non-AI.
3. Run candidate. Green represents a pending prediction, not yet a saved mask. Inspect smoke boundaries and false positives. Choose Add (union), then Apply candidate; or Discard if unacceptable.
4. Click Draw ROI (or Ctrl+R), drag around a missed flame, and choose ROI crop. Fit ROI zooms in; Fit image restores the overall view. A minimum 8 × 8 original-image-pixel rectangle is required. Context defaults to 10% extra width/height per side; reduce it for isolated flames or increase it if surrounding detail helps. Only the original ROI is editable by that candidate.
5. Run again. If the previous candidate is still pending, Yes applies it with the selected merge operation, No discards it and runs, and Cancel keeps it and stops. Applied regions remain in the mask. Change models as needed, repeat on other ROIs, and use Add (union) to accumulate flames. Clear ROI restores Full image; it does not clear the working mask or pending candidate.
6. For SAM2.1, the alternative SAM2 box prompt uses the entire image embedding with a bounding-box prompt; cropped SAM2.1 inference instead encodes the crop and uses the local box. Both accept optional points inside the original ROI. SAM3 uses text for both full and crop modes, not a native box.

## 2. Manual editing

Switch to Edit. Paint fire and Erase operate at the chosen brush size in original RGB pixels. Polygon add/erase uses clicks followed by Finish polygon or Enter. For an existing model mask, choose Select / edit boundary and click near a connected flame component.

- Move: drag a vertex.
- Add: click near an edge to insert a vertex, including the closing edge. Shift-click is an alternate gesture.
- Remove: click a vertex or select one and use Delete selected. A polygon must retain at least three vertices.
- Undo vertex: revert the last temporary edit, or use Ctrl+Z while editing.
- Commit boundary: apply the local rasterized boundary difference. Unedited details, holes and unrelated connected regions are preserved as far as this local edit permits. Cancel edit returns to the original mask.

Boundary vertices are simplified, not a pixel-perfect contour trace. Use the brush for fine flame tips, interior holes or very small details; check at high zoom. Avoid self-crossing polygons and review every committed edit. Undo after committing restores the previous working mask.

## 3. Save and quality control

Save draft while revising; Approve + save after human review. When a candidate is pending, Yes includes it using the selected merge mode; No cancels saving. Discard first if you intend to save without it. Replace and Intersect act only inside the candidate's original ROI in ROI modes, but act globally in Full image mode. Empty destructive predictions require confirmation. Navigation and closing warn before abandoning unsaved edits.

The grayscale PNG labels contain 0 for background and 255 for flame at the original RGB resolution. Overlay JPEGs are inspection aids, not labels. Keep event identity and annotation status; use independent fire-event splits to avoid leakage from near-duplicate photographs. Do not use unreviewed predictions as ground truth.

## 4. Controls

| Gesture | Action |
| --- | --- |
| Mouse wheel | Zoom around pointer |
| Right-button drag | Pan |
| Ctrl+R | Draw ROI |
| Ctrl+Z | Undo vertex or working-mask modification |
| Ctrl+S | Save draft |
| Enter | Finish polygon or commit boundary |
| Escape | Cancel temporary shape |
| Shift-click near edge | Add vertex |
| Delete | Remove selected vertex |

View tab: choose overlay colour/opacity, cyan boundaries, candidate preview visibility, Fit image, or read-only paired IR preview. Hiding the candidate does not discard it. Return to RGB to annotate.
