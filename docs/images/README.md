# Documentation screenshots

These PNG files are versioned documentation assets used by both READMEs:

| File | View |
| --- | --- |
| [brain-map-desktop.png](brain-map-desktop.png) | Overview at a 1440 × 1050 viewport. |
| [brain-map-detail.png](brain-map-detail.png) | The same map with a memory selected. |
| [brain-map-mobile.png](brain-map-mobile.png) | Full-page capture at a 390 × 844 viewport. |

Captured from the actual local HTML in Chromium on 2026-10-16, using this
repository's public project memories and the neutral gray theme. They show the
real interface, rather than a mockup; counts and content are a snapshot.
The map still has known label-overlap and narrow-screen graph-clipping limits.

To refresh the images after an interface change, run `brain map` in this
repository, open `.brain/map.html`, capture the overview and memory selection,
then capture the narrow layout. Save the PNGs under these filenames and inspect
both READMEs. The documentation images are permanent repository files;
temporary browser profiles and test harnesses are not documentation assets.

Generated `.brain/map.html` files stay ignored because they embed a project's
knowledge. Public screenshots must use content intended for publication, as
these do; the agent protocol does not authorize publishing another user's map.
