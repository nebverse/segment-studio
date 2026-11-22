# Annotation policy and controls

**Target:** directly visible RGB flames, not smoke and not fires inferred
behind opaque smoke. Images and source masks remain unmodified; reviewed masks
are saved separately to `firemask_output/`.

## Step-by-step

1. **Open RGB folder** (flat folder of photographs). If saved masks exist they
   are restored automatically when the photograph is opened.
2. Choose `SAM2.1 tiny` / `SAM2.1 small`. Use `SAM positive` clicks on flame and
   `SAM negative` on near-by vegetation/smoke; click `Run candidate`.
   For SAM3, choose `SAM3 text`, enter `flames`, then Run candidate.
3. The green candidate mask is **only a preview**. Use `Apply as`:
   - **Replace:** current mask becomes the new model candidate.
   - **Add (union):** keeps existing flame pixels and adds candidate pixels.
   - **Subtract:** removes candidate pixels from the current mask.
   - **Intersect:** keeps only pixels present in both.
4. Click `Apply candidate` only if appropriate. Undo is available.
5. Use Paint fire / Erase for precise corrections, Polygon add/erase for large
   parts and Edit boundary for larger contour changes. Simplified contour
   vertices may smooth narrow flame edges, so validate at high zoom.
6. Save as draft until validated. Approve + save after human review.

## Editing gestures

- Mouse wheel = zoom around cursor; right-button drag = pan.
- Paint/Erase = drag to add/remove mask pixels. Brush size is in RGB pixels.
- Edit boundary = click near a connected region, drag yellow vertices.
- Shift-click near contour = insert vertex; Delete = remove selected vertex.
- Commit boundary = apply edits, Esc = cancel temporary edit.
- Polygon add/erase = click vertices and press Enter or Finish polygon.
- Ctrl+Z = undo; Ctrl+S = save draft.

## Dataset hygiene

Prefer retaining human-reviewed masks separately from raw model candidates. For
quality evaluation, keep a hold-out group of images or events that are not used
to guide prompt tuning. Record image/event identity, model, reviewer and mask
status. When preparing train/test splits, avoid near-duplicate images from the
same fire event leaking across splits.
