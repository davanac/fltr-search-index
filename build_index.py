#!/usr/bin/env python3
"""
Construit l'index de recherche plein texte du site da.van.ac.

Pourquoi : le moteur natif de Ghost (sodo-search) n'indexe que le titre et
l'extrait — vérifié dans le bundle livré (`index: ['title','excerpt']`), soit
~154 000 signes sur les 4,4 millions publiés, soit 3,5 % du texte. Ce script
construit un index Pagefind sur le texte intégral, servi ensuite en statique
par GitHub Pages.

Chaîne : Content API Ghost (formats=plaintext) -> enregistrements Pagefind
-> dossier `pagefind/` prêt à être publié.

L'index est aussi la préparation de corpus réutilisable pour l'assistant
éditorial : mêmes textes, mêmes métadonnées, même découpage par article.

Aucun secret : la clé du Content API est publique, Ghost la publie dans le
<head> du site. Le script tourne donc sans configuration, y compris dans une
GitHub Action (.github/workflows/reconstruire-index.yml).

Usage :
    python3 build_index.py                 # index complet vers ./pagefind
    python3 build_index.py --limit 50      # échantillon de test
    python3 build_index.py --out /chemin   # autre dossier de sortie
"""

import argparse
import asyncio
import os
import re
import shutil
import sys
import time

import requests

from pagefind.index import PagefindIndex, IndexConfig

SITE_URL = 'https://da.van.ac'
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pagefind')
GHOST_API_DEFAUT = 'https://davanac-team.ghost.io'

# Le Content API plafonne à 100 entrées par page.
PAGE_SIZE = 100
FIELDS = 'id,slug,title,excerpt,url,published_at,visibility,feature_image'


def env(key, defaut=''):
    """Valeur de configuration lue dans l'environnement du process."""
    return os.environ.get(key, defaut)


def resolve_content_key():
    """Clé publique du Content API.

    Elle n'est pas secrète : Ghost la publie dans le <head> de chaque page, sur
    la balise de sodo-search. On lit donc le .env en priorité, et à défaut on la
    récupère depuis le site — ce qui évite une panne silencieuse en cas de
    rotation de la clé.
    """
    cle = env('GHOST_CONTENT_KEY')
    if cle:
        return cle
    html = requests.get(SITE_URL + '/', timeout=30).text
    trouve = re.search(r'sodo-search[^>]*?data-key="([a-f0-9]+)"', html)
    if not trouve:
        raise SystemExit(
            "Clé Content API introuvable : définis GHOST_CONTENT_KEY "
            "(elle est visible dans le <head> de " + SITE_URL + ")."
        )
    return trouve.group(1)


def api_base():
    """Racine de l'API Ghost, déduite de GHOST_API_URL."""
    base = env('GHOST_API_URL', GHOST_API_DEFAUT).rstrip('/')
    if base.endswith('/ghost/api/admin'):
        base = base[: -len('/ghost/api/admin')]
    return base


def fetch_posts(cle, limite=None, verbeux=True):
    """Récupère les articles publiés, texte intégral compris."""
    base = api_base()
    posts, page = [], 1
    while True:
        r = requests.get(
            base + '/ghost/api/content/posts/',
            params={
                'key': cle,
                'limit': PAGE_SIZE,
                'page': page,
                'formats': 'plaintext',
                'fields': FIELDS,
                'include': 'tags',
                'order': 'published_at desc',
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        posts.extend(data['posts'])
        pagination = data['meta']['pagination']
        if verbeux:
            print('  page %d/%d — %d articles' % (page, pagination['pages'], len(posts)))
        if limite and len(posts) >= limite:
            return posts[:limite]
        if not pagination.get('next'):
            return posts
        page = pagination['next']
        time.sleep(0.2)  # courtoisie envers Ghost Pro


def classer(post):
    """Type éditorial d'un article, d'après ses tags.

    Les slugs sont stables, contrairement aux noms : le tag `newsletter`
    s'affiche « First Learn The Rules. Then Break Them ».
    """
    slugs = {t.get('slug') for t in (post.get('tags') or [])}
    if 'newsletter' in slugs:
        return 'newsletter'
    if 'playground' in slugs:
        return 'playground'
    return 'article'


PILIERS = ('souverainete', 'imprevisibilite', 'mobilite', 'factualite', 'solidarite')


def piliers_de(post):
    """Piliers portés par l'article, dans l'ordre canonique du framework."""
    slugs = {t.get('slug') for t in (post.get('tags') or [])}
    return [p for p in PILIERS if p in slugs]


def contenu_indexable(post):
    """Corps soumis à Pagefind.

    Texte brut, sans balises : `add_custom_record` ne passe pas le contenu dans
    un analyseur HTML, il l'indexe tel quel. Une mise en forme `<h1>…</h1>`
    ressortait littéralement dans les extraits de résultats.

    Le titre ouvre l'enregistrement pour rester trouvable, puis l'extrait, puis
    le corps. Les articles réservés aux membres reviennent avec un plaintext
    vide : ils restent indexés sur titre et extrait, jamais sur leur corps.
    """
    morceaux = [(post.get('title') or '').strip(), (post.get('excerpt') or '').strip()]
    for paragraphe in (post.get('plaintext') or '').split('\n'):
        paragraphe = paragraphe.strip()
        if paragraphe:
            morceaux.append(paragraphe)
    return '\n\n'.join(m for m in morceaux if m)


async def _indexer(posts, out_dir):
    """Boucle d'indexation. L'API Python de Pagefind est asynchrone."""
    config = IndexConfig(root_selector='body', force_language='fr', verbose=False)
    async with PagefindIndex(config=config) as index:
        for post in posts:
            piliers = piliers_de(post)
            chemin = post['url'].replace(SITE_URL, '') or '/'
            await index.add_custom_record(
                url=chemin,
                content=contenu_indexable(post),
                language='fr',
                meta={
                    'title': post.get('title') or '',
                    'image': post.get('feature_image') or '',
                    'date': (post.get('published_at') or '')[:10],
                    'acces': post.get('visibility') or 'public',
                    'pilier': piliers[0] if piliers else '',
                },
                filters={
                    'pilier': piliers,
                    'type': [classer(post)],
                    'annee': [(post.get('published_at') or '')[:4]],
                },
                sort={'date': (post.get('published_at') or '')},
            )
        await index.write_files(output_path=out_dir)


def build(posts, out_dir, verbeux=True):
    """Indexe les articles et écrit le dossier `pagefind/`."""
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    asyncio.run(_indexer(posts, out_dir))

    if verbeux:
        total = 0
        for racine, _, fichiers in os.walk(out_dir):
            for f in fichiers:
                total += os.path.getsize(os.path.join(racine, f))
        nb = sum(len(f) for _, _, f in os.walk(out_dir))
        print('Index écrit : %s' % out_dir)
        print('  %d fichiers, %.1f Mo' % (nb, total / 1_000_000))
    return out_dir


def main():
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument('--out', default=DEFAULT_OUT, help='dossier de sortie')
    parseur.add_argument('--limit', type=int, help='ne traiter que les N articles les plus récents')
    parseur.add_argument('--quiet', action='store_true')
    args = parseur.parse_args()

    verbeux = not args.quiet
    cle = resolve_content_key()
    if verbeux:
        print('Récupération des articles depuis %s' % api_base())
    posts = fetch_posts(cle, limite=args.limit, verbeux=verbeux)

    signes = sum(len(p.get('plaintext') or '') for p in posts)
    if verbeux:
        print('%d articles, %.1f M signes de texte' % (len(posts), signes / 1_000_000))
        print('Construction de l\'index Pagefind…')

    build(posts, os.path.abspath(args.out), verbeux=verbeux)
    return 0


if __name__ == '__main__':
    sys.exit(main())
