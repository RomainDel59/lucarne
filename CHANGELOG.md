# Changelog

All notable changes to Lucarne are documented in this file.

## 1.1.0

- Rewrite the web interface with Nextcloud components so it looks and behaves like the other Nextcloud apps and follows the light, dark and custom themes.
- Show two complete rows of videos per page whatever the width, with icon-only pagination buttons that stay at the same place.
- Show subscriptions and playlists in a paginated grid, with icon menus to sort and filter them.
- Use the full width in the catalogues, settings, administration and supervision pages, with form buttons aligned to the right.
- Supervision: inline action buttons, clearer details toggle, and rows that no longer look clickable.
- Video page: full-width player with a capped height, thumbnails never cropped or stretched, picture-in-picture disabled.
- Add a 64 kbps audio quality and allow batches as small as one video.
- Build the front-end in the Docker image.

## 1.0.1

- Fix the first subscription never synchronizing: the agent no longer ends a campaign while it still has queued batches, so the pacing timer can reach zero.
- Update python-multipart to 0.0.31 to address published security advisories.

## 1.0.0

- Initial AppAPI external application release.
- Add channel subscriptions, personal and YouTube playlists, catalogues, history, and playback preferences.
- Add sequential catalogue campaigns, visible batch supervision, and configurable collection pacing.
- Add temporary and retained local media with range-capable playback.
- Add English and French interfaces.

