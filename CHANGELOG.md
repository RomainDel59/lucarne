# Changelog

All notable changes to Lucarne are documented in this file.

## 1.0.1

- Fix the first subscription never synchronizing: the agent no longer ends a campaign while it still has queued batches, so the pacing timer can reach zero.
- Update python-multipart to 0.0.31 to address published security advisories.

## 1.0.0

- Initial AppAPI external application release.
- Add channel subscriptions, personal and YouTube playlists, catalogues, history, and playback preferences.
- Add sequential catalogue campaigns, visible batch supervision, and configurable collection pacing.
- Add temporary and retained local media with range-capable playback.
- Add English and French interfaces.

