# Contributing

Thank you for improving Lucarne.

## Ground rules

- Keep repository content, code, comments, logs, and documentation in English.
- Keep English as the source UI language and update French translations for user-visible changes.
- Preserve user isolation in every query and file operation.
- Avoid unbounded YouTube requests. Collection work must remain batched and sequential.
- Add tests for behavior changes and security boundaries.
- Do not add analytics, advertisements, tracking pixels, or YouTube account requirements.
- In the web interface, reuse Nextcloud components, icons and theme variables instead of declaring new styles. Only elements Nextcloud does not provide, such as video thumbnails, have their own styles, and those read Nextcloud CSS variables directly.

## Checks

Run before opening a pull request:

```sh
ruff check src tests
pytest
(cd frontend && npm ci && npm run build)
docker build -t lucarne:test .
```

Keep changes focused and explain any storage or API compatibility impact in the pull request.

## Web interface

The interface is a Vue 3 application in `frontend/`, built with Vite into `static/js/lucarne-main.js` and `static/css/lucarne.css`. These two generated files are not committed. Run `npm run build` in `frontend/` to produce them for a local run, or `npm run dev` to rebuild on every change. The Docker image builds them itself.

Keep `@nextcloud/vue` and the related libraries on the versions used by the Nextcloud release you target, so the interface looks exactly like the other apps. Every translatable string is written as `t('English text')` and must exist in `static/i18n/fr.json`; a test checks it.

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

