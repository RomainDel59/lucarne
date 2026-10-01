[🇬🇧 English](../../README.md) | 🇫🇷 **Français**

# Lucarne

Lucarne est une vidéothèque YouTube privée et sobre pour Nextcloud. Elle suit des chaînes, importe des playlists, range les abonnements dans des catalogues et lit les médias depuis une interface calme, sans compte YouTube.

Lucarne est une application externe AppAPI de Nextcloud. Son API, son agent de catalogues, son téléchargeur de médias, sa base de données et son interface web tournent dans un seul conteneur. AppAPI fournit un volume persistant isolé pour la base SQLite, les images en cache, les téléchargements temporaires et les médias conservés.

## Prérequis

- Nextcloud 35 ou 36
- AppAPI avec un démon de déploiement HaRP fonctionnel
- Un hôte pris en charge par le déploiement de conteneurs AppAPI

## Installation

Enregistrez la dernière version publiée (v1.1.0) auprès d'AppAPI, avec le fichier `appinfo/info.xml` de son tag. Remplacez `<démon>` par le nom de votre démon de déploiement HaRP :

```sh
php occ app_api:app:register lucarne <démon> --info-xml https://raw.githubusercontent.com/RomainDel59/lucarne/v1.1.0/appinfo/info.xml --wait-finish
```

AppAPI télécharge et démarre ensuite automatiquement l'image de conteneur correspondante.

## Fonctionnalités

- Pages de vidéos chronologiques affichant deux rangées complètes par page, avec des boutons précédent et suivant en icônes seules
- Abonnements à des chaînes et playlists YouTube ou personnelles, en grilles paginées qui se trient et se filtrent
- Catalogues classés par ordre alphabétique et vue automatique des vidéos sans catalogue
- Qualité de lecture (vidéo jusqu'à 1080p, audio de 64 à 256 kbps), mode audio, profondeur d'historique et appartenance aux catalogues propres à chaque utilisateur
- Téléchargement et lecture immédiats, avec prise en charge des requêtes HTTP par plage
- Conservation temporaire glissante des médias et conservation hors ligne optionnelle
- Campagnes de catalogue persistantes et respectueuses des limites de débit, avec supervision visible des lots
- Interface construite avec les composants Nextcloud, qui suit le thème clair, sombre ou personnalisé de chaque utilisateur
- Anglais comme langue source et traduction française incluse
- Isolation multi-utilisateur dès le premier enregistrement

## Exécuter une version de développement

Construisez l'image et enregistrez `appinfo/info.xml` auprès d'un démon de déploiement AppAPI de développement :

```sh
docker build -t ghcr.io/romaindel59/lucarne:dev .
```

L'image contient Python, FastAPI, `yt-dlp` avec son résolveur de défis EJS, Deno, FFmpeg, l'interface web compilée et le client FRP de HaRP. Aucun conteneur de traitement ni aucune base de données supplémentaire n'est nécessaire.

Pour essayer Lucarne dans un Nextcloud jetable, suivez la section « Try Lucarne in a local Nextcloud » de [CONTRIBUTING.md](../../CONTRIBUTING.md) (en anglais).

## Organisation des données

AppAPI expose le volume de l'application via `APP_PERSISTENT_STORAGE`. Lucarne y crée :

```text
lucarne.db
channel-images/
playlist-images/
thumbnails/
downloads/
library/
```

Sauvegardez le volume AppAPI avec la même politique que pour les autres données d'application. L'image du conteneur elle-même est jetable.

## Développement

Créez un environnement Python 3.12 et installez les dépendances de développement :

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest
ruff check src tests
```

Validez une construction proche de la production avec :

```sh
docker build --pull -t lucarne:test .
docker run --rm --entrypoint python lucarne:test -m compileall -q /app/src
```

Le client web est une application Vue construite avec les mêmes composants Nextcloud que l'application Fichiers (`@nextcloud/vue`), donc elle suit le thème appliqué dans Nextcloud. Ses sources sont dans `frontend/`. La construction Docker les compile en un seul script et une seule feuille de style, `static/js/lucarne-main.js` et `static/css/lucarne.css`, servis par le proxy AppAPI authentifié. Ces deux fichiers générés ne sont pas versionnés ; pour les construire hors de Docker, utilisez Node.js 20.11 ou plus récent :

```sh
cd frontend
npm ci
npm run build
```

Les bibliothèques du front-end sont figées aux versions utilisées par Nextcloud 35.

## Localisation

Les textes anglais sont les textes sources, écrits `t('English text')` dans l'interface web. Les traductions de l'interface web à l'exécution se trouvent dans `static/i18n/<langue>.json`, où `en.json` est vide car l'anglais n'a pas besoin de traduction ; les traductions des métadonnées de l'application Nextcloud se trouvent dans `l10n/`.

Pour ajouter une langue :

1. Copiez `static/i18n/fr.json` sous le nom de la nouvelle langue.
2. Traduisez chaque valeur sans modifier les clés ni les marqueurs tels que `{count}`.
3. Ajoutez les fichiers Nextcloud correspondants `l10n/<langue>.json` et `.js`.
4. Ajoutez le code de la langue à `SUPPORTED_LANGUAGES` dans `src/localization.py`.

## Modèle de sécurité

- AppAPI authentifie chaque requête d'API, de média, de script, de style et d'image.
- Chaque requête de base de données portant sur des données d'un utilisateur inclut son identifiant Nextcloud.
- Les URL YouTube saisies sont normalisées et limitées à des hôtes et chemins HTTPS approuvés.
- Les images distantes sont limitées aux hôtes d'images publics de YouTube et bornées en taille.
- Les chemins des médias sont générés par Lucarne et jamais acceptés du client.
- Les routes d'administration sont déclarées avec le niveau d'accès `ADMIN` d'AppAPI.

Merci de signaler les problèmes de sécurité selon [SECURITY.md](../../SECURITY.md) (en anglais).

## Licence

Lucarne est distribuée sous la licence GNU Affero General Public License, version 3 ou ultérieure.
