# Changelog

All notable changes to Lucarne are documented in this file.

## 1.3.1

- Read the reason of every YouTube failure in English, whatever the language chosen for titles, so private, removed, members-only, age-restricted and not yet released videos are recognized the same way.
- Keep a hidden record of the videos that could not be read, with the reason given by YouTube, instead of failing the whole batch and repeating the same error. Videos that are not yet released are tried again at their release date, and the others at spaced intervals for a week.
- Add an administration option to show these videos, flagged as skipped, in the lists. Their page gives the reason and a Retry button, and the date falls back to the day they were found, with a tooltip.
- Upgrading from 1.3.0 migrates the database automatically (schema version 6).

## 1.3.0

- Drag a subscription from the Subscriptions page onto a catalogue of the navigation to add it, without leaving its other catalogues. A notification tells when the channel is added, or that it is already there.
- While viewing the subscriptions of one catalogue, drag a subscription onto the removal zone at the bottom of the page to take it out of that catalogue only.
- The navigation has a Playlists menu, closed by default, listing every playlist. Drag a video tile onto a personal playlist to add it. Playlists imported from YouTube do not accept dropped videos.
- Personal playlists are ordered by hand: a video is added at the end, and dragging a tile before or after another one of the page changes the order. Videos are removed by dragging them onto the removal zone, which replaces the removal button of the tiles. Playlists imported from YouTube follow the order of YouTube. Personal playlists no longer follow the publication date, so their existing videos now appear in the order they were added.
- Add a button to open a channel, a video or an imported playlist on YouTube.
- Keep the channel and the date of a video tile on one line, with an ellipsis and a tooltip on a long channel name.
- Make the add catalogue button primary.
- Fix an imported playlist being named after its owner instead of its own title.
- Skip premieres and live events that have not started, like private videos, instead of failing the subscription.
- Upgrading from 1.2.0 migrates the database automatically (schema version 4).

## 1.2.0

- Follow each user's Nextcloud language and locale for the interface, error messages, and dates, instead of the browser's.
- Fetch YouTube titles and descriptions in a language chosen by the administrator (English or French) instead of always in French. It is initialized from the Nextcloud language of the first administrator, and English is used until an administrator opens Lucarne.
- Prepare the store listing: clearer summary and description, identifiable author, documentation link, screenshots, and a third-party services notice in the README.
- Upgrading from 1.1.0 migrates the database automatically (schema version 3).

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

