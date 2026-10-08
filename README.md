# flag2md

Transforme tes sessions de CTF en write-ups Markdown propres, sans tout réécrire à la fin.

Le principe : tu prends tes notes **pendant** que tu résous. Chaque commande lancée, chaque idée,
chaque script et chaque capture d'écran est ajouté au fichier `notes.md` du challenge. À la fin,
`flag2md build` assemble le tout avec l'énoncé, les fichiers fournis et le flag pour produire le
write-up final.

## Installation

Python 3.10 ou plus récent.

```bash
git clone https://github.com/paul7436/flag2md
cd flag2md
pipx install .          # ou : uv tool install .   ou : pip install -e .
```

Vérifier que tout marche :

```bash
flag2md --version
```

## Démarrage rapide

```bash
# 1. Créer le dossier du CTF
flag2md init "FCSC 2026" --url https://ctf.exemple.fr
cd fcsc-2026

# 2. Récupérer les challenges depuis CTFd (ou les créer à la main)
flag2md pull -t <ton_token_ctfd>
flag2md new "Baby ROP" -c pwn -p 200

# 3. Résoudre en notant au fur et à mesure
cd pwn/baby-rop
flag2md run checksec --file=./baby_rop
flag2md run "strings baby_rop | grep -i flag"
flag2md note "Pas de canary et NX actif : on part sur un ret2libc."
flag2md add ~/exploits/solve.py ~/Images/leak.png
flag2md flag "FCSC{r0p_1s_fun}"

# 4. Générer le write-up et l'index du CTF
flag2md build
```

## Organisation des dossiers

```text
fcsc-2026/
|-- ctf.yml                 infos du CTF (nom, url, équipe, dates, réglages)
|-- README.md               index généré : challenges par catégorie, résolus ou non
`-- pwn/
    `-- baby-rop/
        |-- challenge.yml   infos du challenge (énoncé, points, flag, statut...)
        |-- notes.md        TES notes : c'est ici que tu écris
        |-- README.md       write-up généré à partir de notes.md
        |-- files/          fichiers fournis par les organisateurs
        |-- solve/          tes scripts
        `-- assets/         tes captures d'écran
```

`README.md` est regénéré à chaque `build` : écris toujours dans `notes.md`, jamais dans
`README.md`.

## Commandes

| Commande | Rôle |
| --- | --- |
| `init NOM` | Crée le dossier du CTF et son `ctf.yml` |
| `new NOM` | Crée un challenge dans le CTF courant |
| `pull` | Récupère les challenges depuis la plateforme (CTFd) |
| `run CMD` | Lance une commande, affiche sa sortie et la note dans `notes.md` |
| `note TEXTE` | Ajoute une note libre (Markdown) |
| `add FICHIERS` | Ajoute des scripts ou des images au write-up |
| `flag FLAG` | Enregistre le flag et marque le challenge comme résolu |
| `build` | Génère le write-up et l'index du CTF |
| `ls` | Liste les challenges du CTF avec leur statut |
| `config` | Affiche les réglages utilisés et leur provenance |

`flag2md <commande> --help` donne toutes les options.

Les commandes `run`, `note`, `add`, `flag` et `build` cherchent le challenge dans le dossier courant
(ou ses parents). Pour viser un autre challenge : `--chal chemin/vers/le/challenge`.

### init

```bash
flag2md init "FCSC 2026" --url https://ctf.exemple.fr --team MaTeam --start 2026-04-11 --end 2026-04-21
```

Le dossier prend le nom du CTF en minuscules sans espaces (`fcsc-2026`). `--dir` pour en choisir un
autre.

### new

```bash
flag2md new "Baby ROP" -c pwn -p 200 -a auteur -t rop -t easy \
    -d "Énoncé du challenge" -n "nc challenges.fcsc.fr 2101"
```

Crée `pwn/baby-rop/` avec `challenge.yml` et un `notes.md` vide. Tu peux aussi compléter
`challenge.yml` à la main.

### run

```bash
flag2md run checksec --file=./baby_rop
flag2md run "cat dump.txt | base64 -d | xxd | head"
```

- La sortie s'affiche en direct et est ajoutée à `notes.md` dans un bloc de code, avec la commande.
- Une seule chaîne entre guillemets passe par le shell : les pipes et redirections marchent.
- Les couleurs du terminal sont retirées, les longues sorties sont coupées au milieu
  (`max_output_lines`, 80 lignes par défaut).
- Un code de retour non nul est noté (`[exit 1]`). Après un Ctrl+C, ce qui a déjà été affiché est
  quand même enregistré.
- Pour les outils interactifs (gdb, nc), lance-les normalement et note le résultat avec `note`.

### note

```bash
flag2md note "Le binaire lit 0x100 octets dans un buffer de 0x40."
flag2md note                     # ouvre ton $EDITOR pour une note longue
echo "texte" | flag2md note      # lit l'entrée standard
```

Le texte est du Markdown : titres, listes, code, tout est permis.

### add

```bash
flag2md add solve.py leak.png
flag2md add notes_gdb.txt --to annexes
flag2md add leak.png --caption "Fuite de l'adresse de puts"
```

- Les images sont copiées dans `assets/` et affichées dans le write-up.
- Les scripts et fichiers texte sont copiés dans `solve/`. Leur contenu est inséré dans le
  write-up au moment du `build`, donc c'est toujours la dernière version de ton exploit qui
  apparaît.
- Les fichiers binaires sont simplement mis en lien.
- Un fichier déjà présent dans le dossier du challenge n'est pas copié, juste référencé.

### flag

```bash
flag2md flag "FCSC{r0p_1s_fun}"
```

Enregistre le flag, passe le statut à `solved` et note la date de résolution.

### build

```bash
flag2md build          # dans un challenge : ce challenge + l'index du CTF
flag2md build --all    # tous les challenges du CTF
```

Depuis la racine du CTF, `build` regénère tous les challenges.

### pull

```bash
flag2md pull -t <token>                 # token d'API CTFd
flag2md pull --session <cookie>         # ou la valeur du cookie "session"
flag2md pull -c web -c crypto           # seulement certaines catégories
flag2md pull --no-files                 # sans télécharger les pièces jointes
flag2md pull --max-size 20              # ignore les fichiers de plus de 20 Mo
flag2md pull --force                    # retélécharge les fichiers déjà présents
```

- Récupère l'énoncé, les points, le nombre de résolutions, les tags, les indices débloqués, les
  infos de connexion et les pièces jointes (avec leur SHA256).
- Les challenges que tu as déjà résolus sur la plateforme sont marqués comme résolus.
- Tu peux relancer `pull` autant que tu veux : tes notes, ton flag et ton statut sont conservés.
- Le token CTFd se génère dans les paramètres de ton compte sur la plateforme.

## Exemple de write-up généré

Avec la session du démarrage rapide, `pwn/baby-rop/README.md` ressemble à ça :

````markdown
# Baby ROP

| CTF | Catégorie | Points | Résolutions | Auteur |
| --- | --- | --- | --- | --- |
| FCSC 2026 | pwn | 200 | - | - |

**Tags:** `rop`

## Énoncé

> Un binaire, un service, un flag.

## Connexion

```text
nc challenges.fcsc.fr 2101
```

## Résolution

```console
$ checksec --file=./baby_rop
Canary: No / NX: Yes
```

Pas de canary et NX actif : on part sur un ret2libc.

`solve/solve.py`

```python
from pwn import *

io = remote("challenges.fcsc.fr", 2101)
```

## Flag

```text
FCSC{r0p_1s_fun}
```
````

Et l'index du CTF (`fcsc-2026/README.md`) :

```markdown
# FCSC 2026

| Date | Équipe | Résolus | Points |
| --- | --- | --- | --- |
| 2026-04-11 | - | 1/1 | 200 |

## pwn

- [x] [Baby ROP](pwn/baby-rop/README.md) (200 pts)
```

## Configuration

Les réglages se lisent dans cet ordre, le dernier gagne :

1. les valeurs par défaut ;
2. le fichier global `~/.config/flag2md/config.yml` ;
3. la section `settings` du `ctf.yml` du CTF courant.

| Clé | Défaut | Rôle |
| --- | --- | --- |
| `author` | vide | Ton pseudo, utilisé dans le front matter |
| `lang` | `fr` | Langue des titres du write-up : `fr` ou `en` |
| `frontmatter` | `none` | En-tête pour blog : `none`, `hugo` ou `jekyll` |
| `writeup_file` | `README.md` | Nom du write-up généré dans chaque challenge |
| `index_file` | `README.md` | Nom de l'index généré à la racine du CTF |
| `max_output_lines` | `80` | Lignes gardées par commande `run` (0 : tout garder) |
| `templates_dir` | vide | Dossier de templates personnalisés |
| `tokens` | vide | Tokens d'API par domaine, pour `pull` |

Exemple de `~/.config/flag2md/config.yml` :

```yaml
author: monpseudo
lang: fr
frontmatter: hugo
tokens:
  ctf.exemple.fr: ctfd_0123456789abcdef
```

Exemple de `ctf.yml` avec des réglages propres à ce CTF :

```yaml
name: FCSC 2026
url: https://ctf.exemple.fr
platform: ctfd
team: MaTeam
start: '2026-04-11'
end: '2026-04-21'
settings:
  lang: en
  frontmatter: jekyll
```

Pour le token, l'ordre est : option `-t`, puis variable d'environnement `FLAG2MD_TOKEN`, puis
`tokens` dans la config globale. Ne le mets jamais dans `ctf.yml` : ce fichier finit souvent
publié avec tes write-ups. Le cookie de session peut aussi passer par `FLAG2MD_SESSION`.

### Publier sur un blog

- **Hugo** : `frontmatter: hugo` et `writeup_file: index.md` pour avoir un dossier par article.
- **Jekyll** : `frontmatter: jekyll` ajoute `layout: post`, le titre, la date, les catégories et
  les tags.
- **GitHub** : rien à régler, les `README.md` s'affichent directement dans le repo.

## Templates personnalisés

Le rendu passe par deux templates Jinja2 :

- `writeup.md.j2` pour chaque challenge ;
- `index.md.j2` pour l'index du CTF.

Pour changer la mise en page, copie celui que tu veux depuis `src/flag2md/templates/` dans
`~/.config/flag2md/templates/` (pour tous tes CTF) ou dans le dossier indiqué par `templates_dir`
(pour un seul CTF), puis modifie la copie. Un template absent de ces dossiers reprend la version
intégrée.

Variables disponibles dans `writeup.md.j2` :

| Variable | Contenu |
| --- | --- |
| `chal` | Le challenge : `name`, `category`, `points`, `solves`, `author`, `description`, `connection_info`, `tags`, `hints`, `flag`, `status`, `solved`, `solved_at` |
| `ctf` | Le CTF (`name`, `url`, `team`, `start`, `end`), ou rien si le challenge est hors CTF |
| `notes` | Le contenu de `notes.md`, scripts déjà insérés |
| `files` | Pièces jointes : `name`, `size`, `sha256`, `link` |
| `front_matter` | L'en-tête de blog déjà prêt, ou une chaîne vide |
| `L` | Les titres traduits (`L.description`, `L.solution`, `L.flag`...) |
| `settings` | Tous les réglages |

Dans `index.md.j2` : `ctf`, `groups` (chaque groupe a `category` et `challenges`, avec `name`,
`points`, `solved`, `link`), `total`, `solved`, `points`, `dates`, `front_matter`, `L`, `settings`.

Filtres ajoutés : `quote_block` (citation Markdown), `cell` (protège les `|` dans un tableau),
`code` (entoure de backticks) et `human_size` (taille lisible).

## Ajouter une plateforme

`pull` gère CTFd pour l'instant. Pour une autre plateforme, crée une classe dans
`src/flag2md/platforms/` qui hérite de `Platform` (voir `base.py`) avec trois méthodes :

- `list_challenges()` : la liste des challenges visibles ;
- `get_challenge(id)` : le détail d'un challenge ;
- `download(fichier, destination, max_bytes)` : le téléchargement d'une pièce jointe.

Puis ajoute-la dans `PLATFORMS` dans `src/flag2md/platforms/__init__.py`. Le champ `platform` du
`ctf.yml` choisit la plateforme utilisée.

## Développement

```bash
pip install -e ".[dev]"
pytest
```
