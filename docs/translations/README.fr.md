[🇬🇧 English](../../README.md) | 🇫🇷 **Français**

# Lucarne

Lucarne est une vidéothèque YouTube privée et sobre pour Nextcloud. Elle suit des chaînes, importe des playlists, range les abonnements dans des catalogues et lit les médias depuis une interface calme, sans compte YouTube.

Lucarne est une application externe AppAPI de Nextcloud. Son API, son agent de catalogues, son téléchargeur de médias, sa base de données et son interface web tournent dans un seul conteneur. AppAPI fournit un volume persistant isolé pour la base SQLite, les images en cache, les téléchargements temporaires et les médias conservés.

![Page d'accueil de Lucarne : une grille des vidéos récentes](../screenshot-home.png)

![Page des abonnements de Lucarne : les chaînes avec leur nombre de vidéos et leur dernière date](../screenshot-subscriptions.png)

## Prérequis

- Nextcloud 35 ou 36
- AppAPI avec un démon de déploiement HaRP fonctionnel
- Un hôte pris en charge par le déploiement de conteneurs AppAPI

## Installation

Enregistrez la dernière version publiée (v1.3.1) auprès d'AppAPI, avec le fichier `appinfo/info.xml` de son tag. Remplacez `<démon>` par le nom de votre démon de déploiement HaRP :

```sh
php occ app_api:app:register lucarne <démon> --info-xml https://raw.githubusercontent.com/RomainDel59/lucarne/v1.3.1/appinfo/info.xml --wait-finish
```

AppAPI télécharge et démarre ensuite automatiquement l'image de conteneur correspondante.

Une fois l'installation faite, un administrateur doit ouvrir Lucarne une première fois. La langue des titres et descriptions YouTube est un réglage unique de l'instance : elle est initialisée avec la langue Nextcloud du premier administrateur et se change dans Administration (anglais ou français). Tant qu'elle n'est pas initialisée, l'anglais est utilisé.

L'image contient Python, FastAPI, `yt-dlp` avec son résolveur de défis EJS, Deno, FFmpeg, l'interface web compilée et le client FRP de HaRP. Aucun conteneur de traitement ni aucune base de données supplémentaire n'est nécessaire.


## Fonctionnalités

- Pages de vidéos chronologiques affichant deux rangées complètes par page, avec des boutons précédent et suivant en icônes seules
- Abonnements à des chaînes et playlists YouTube ou personnelles, en grilles paginées qui se trient et se filtrent
- Catalogues classés par ordre alphabétique et vue automatique des vidéos sans catalogue ; glissez un abonnement sur un catalogue du menu pour l'y ajouter, ou sur la zone de retrait pour l'enlever du catalogue affiché
- Playlists personnelles dans l'ordre de votre choix : glissez des vidéos sur une playlist du menu pour les y ajouter, et une tuile avant ou après une autre pour les réordonner. Les playlists importées de YouTube gardent l'ordre de YouTube
- Lien pour ouvrir sur YouTube n'importe quelle chaîne, vidéo ou playlist importée
- Qualité de lecture (vidéo jusqu'à 1080p, audio de 64 à 256 kbps), mode audio, profondeur d'historique et appartenance aux catalogues propres à chaque utilisateur
- Téléchargement et lecture immédiats, avec prise en charge des requêtes HTTP par plage
- Conservation temporaire glissante des médias et conservation hors ligne optionnelle
- Campagnes de catalogue persistantes et respectueuses des limites de débit, avec supervision visible des lots
- Interface construite avec les composants Nextcloud, qui suit le thème clair, sombre ou personnalisé de chaque utilisateur
- La langue de l'interface et les formats de date suivent les paramètres Nextcloud de chaque utilisateur ; la langue des titres et descriptions YouTube est un réglage d'administration
- Anglais comme langue source et traduction française incluse
- Isolation multi-utilisateur dès le premier enregistrement

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

## Contribuer

L'environnement de développement, les vérifications, l'environnement Nextcloud local et les étapes pour ajouter une langue sont décrits dans [CONTRIBUTING.md](../../CONTRIBUTING.md) (en anglais).

## Modèle de sécurité

- AppAPI authentifie chaque requête d'API, de média, de script, de style et d'image.
- Chaque requête de base de données portant sur des données d'un utilisateur inclut son identifiant Nextcloud.
- Les URL YouTube saisies sont normalisées et limitées à des hôtes et chemins HTTPS approuvés.
- Les images distantes sont limitées aux hôtes d'images publics de YouTube et bornées en taille.
- Les chemins des médias sont générés par Lucarne et jamais acceptés du client.
- Les routes d'administration sont déclarées avec le niveau d'accès `ADMIN` d'AppAPI.

Merci de signaler les problèmes de sécurité selon [SECURITY.md](../../SECURITY.md) (en anglais).

## Services tiers

Le serveur de Lucarne contacte YouTube pour lire les informations des chaînes, des playlists et des vidéos et pour récupérer les médias que vous lisez, et il télécharge des images depuis les hôtes d'images publics de YouTube. Lucarne ne contient ni statistiques d'usage, ni publicité, ni suivi, et n'exige pas de compte YouTube.

Votre usage de YouTube reste soumis à ses conditions d'utilisation : il vous revient de les respecter, ainsi que le droit d'auteur. Lucarne n'est affiliée ni à YouTube ni à Nextcloud, et n'est approuvée par aucun des deux.

## Licence

Lucarne est distribuée sous la licence GNU Affero General Public License, version 3 ou ultérieure.
