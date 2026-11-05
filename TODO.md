# Possible TODO items

Ideas parked for later, not yet committed to.

## Upstream

### gramps-web (frontend): face tagging is hard to use

Found 2026-11-05 while tagging faces in a group photo.

- The media region editor has no Save button, tooltips or hints. Picking a
  person in the **Link** field saves the region straight away, which isn't
  obvious. The **Replace file** upload just below looks like the save action,
  but it replaces the photo's file.
- If the person already has the whole photo (added with "share existing"),
  linking a face *adds* a second media reference with the face rectangle at
  the end of the person's media list (`addMediaRegion` in `src/util.js`). The
  uncropped reference stays first, so the profile picture and chart thumbnail
  are still the whole group. The uncropped reference has to be deleted by hand.
  Better: set the rectangle on the existing uncropped reference, or put the
  new one first, or offer to.
- Files: `src/components/GrampsjsMediaObject.js`,
  `src/views/GrampsjsViewMedia.js`, `src/util.js`.

## This project

### Drop cache-clearing workarounds once upstream fixes are released

Since Flask-Caching 2.5, gramps-webapi caches error responses.

- `mk-addons` clears the request cache. Fixed upstream in
  gramps-web-api#1144, released in 3.25.2.
- `mk-backend` clears the thumbnail cache. Fix proposed in
  gramps-web-api#1158.

The workarounds are harmless, so remove them only after the fixes are in a
release the installer uses.
