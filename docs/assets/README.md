# Documentation Assets

* `stories/us_NN_expected.png` — reference screenshots used during the Phase 3
  manual walkthrough. Regenerate them from the checked-in UI mock states with:
  `python3 scripts/render_story_assets.py`.
* `demo.gif` — short capture of the end-to-end flow, linked from `../usage.md`.

To capture a screenshot on macOS:

```bash
python3 scripts/render_story_assets.py
```

The renderer uses headless Chrome to create stable PNGs that match the app's
documented walkthrough states.
