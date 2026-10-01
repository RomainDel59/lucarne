# Contributing

Thank you for improving Lucarne.

## Ground rules

- Keep repository content, code, comments, logs, and documentation in English. The README is the only document that is translated: translations live in `docs/translations/` as `README.<language>.md` and must be updated together with `README.md`.
- Keep English as the source UI language and update French translations for user-visible changes.
- Preserve user isolation in every query and file operation.
- Avoid unbounded YouTube requests. Collection work must remain batched and sequential.
- Add tests for behavior changes and security boundaries.
- Do not add analytics, advertisements, tracking pixels, or YouTube account requirements.
- In the web interface, reuse Nextcloud components, icons and theme variables instead of declaring new styles. Only elements Nextcloud does not provide, such as video thumbnails, have their own styles, and those read Nextcloud CSS variables directly.

## Checks

Create a Python 3.12 environment and install the development dependencies:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
```

Run before opening a pull request:

```sh
ruff check src tests
pytest
(cd frontend && npm ci && npm run build)
docker build --pull -t lucarne:test .
docker run --rm --entrypoint python lucarne:test -m compileall -q /app/src
```

Keep changes focused and explain any storage or API compatibility impact in the pull request.

## Web interface

The interface is a Vue 3 application in `frontend/`, built with Vite into `static/js/lucarne-main.js` and `static/css/lucarne.css`. These two generated files are not committed. Run `npm run build` in `frontend/` to produce them for a local run, or `npm run dev` to rebuild on every change. The Docker image builds them itself. Building them outside Docker requires Node.js 20.11 or later.

Keep `@nextcloud/vue` and the related libraries on the versions used by the Nextcloud release you target, so the interface looks exactly like the other apps. Every translatable string is written as `t('English text')` and must exist in `static/i18n/fr.json`; a test checks it.

## Localization

The interface language is the Nextcloud language of the user: the front-end sends it as the `Accept-Language` header of every request, and the dates use the Nextcloud locale. The server remembers it per user so the catalogue agent fetches YouTube titles and descriptions in the same language. English strings are the source strings, written as `t('English text')` in the web interface. Runtime web translations live in `static/i18n/<language>.json`, where `en.json` is empty because English needs no translation; Nextcloud application metadata translations live in `l10n/`.

When adding a language:

1. Copy `static/i18n/fr.json` to the new locale name.
2. Translate every value without changing the keys or placeholders such as `{count}`.
3. Add the matching Nextcloud `l10n/<language>.json` and `.js` files.
4. Add the language code to `SUPPORTED_LANGUAGES` in `src/localization.py`.

## Releasing

For each release:

1. Set the new version everywhere it appears: `appinfo/info.xml` (`version` and `image-tag`), `pyproject.toml`, `src/__init__.py`, `src/main.py`, `frontend/package.json`, `frontend/package-lock.json`, and `frontend/vite.config.js`.
2. Update the version in the installation command of `README.md` and its translations.
3. Add the release to `CHANGELOG.md`.
4. Merge, then push the tag `v<version>`. The workflow publishes the container image.

Lucarne is not published in the Nextcloud App Store yet. The store follows the [publishing procedure of the Nextcloud developer manual](https://docs.nextcloud.com/server/latest/developer_manual/app_publishing_maintenance/publishing.html): a signing certificate for the app ID is requested once through the `nextcloud/app-certificate-requests` repository, and each release is an archive (a single top-level `lucarne` folder containing `appinfo/info.xml`) that is signed and uploaded once the container image exists.

## Try Lucarne in a local Nextcloud

`dev/docker-compose.yml` starts a disposable Nextcloud 35 with PostgreSQL and the HaRP proxy used by AppAPI. It is for local development only: credentials are trivial, so never expose it to a network. Ports `8080`, `8780`, and `8782` must be free.

Start the stack and wait until Nextcloud is installed (a few minutes on first start):

```sh
docker compose -f dev/docker-compose.yml up -d
docker compose -f dev/docker-compose.yml exec -u www-data nextcloud php occ status
```

Register the HaRP deploy daemon, then install Lucarne:

```sh
docker compose -f dev/docker-compose.yml exec -u www-data nextcloud php occ \
  app_api:daemon:register harp_dev "HaRP (dev)" docker-install http harp:8780 http://nextcloud \
  --net lucarne-dev --harp --harp_frp_address harp:8782 --harp_shared_key dev-only-shared-key --set-default

docker compose -f dev/docker-compose.yml exec -u www-data nextcloud php occ \
  app_api:app:register lucarne harp_dev --info-xml /lucarne/info.xml --wait-finish
```

With Git Bash on Windows, prefix these commands with `MSYS_NO_PATHCONV=1` so `/lucarne/info.xml` is not rewritten into a Windows path.

Open <http://localhost:8080> and sign in as `admin` with password `admin`. Lucarne appears in the top menu. The installed image is the one referenced by `appinfo/info.xml`, so it is the published release rather than your working tree.

Remove everything, including volumes and the application container, when finished:

```sh
docker compose -f dev/docker-compose.yml exec -u www-data nextcloud php occ app_api:app:unregister lucarne
docker compose -f dev/docker-compose.yml down -v
```

