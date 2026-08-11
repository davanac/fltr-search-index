# fltr-search-index

Index de recherche plein texte du site [da.van.ac](https://da.van.ac) — le site de Damien Van Achter (davanac).

Ce dépôt ne contient **pas** de contenu éditorial : uniquement un index [Pagefind](https://pagefind.app/) construit à partir des articles **déjà publics** du site. Il est public parce qu'un index de recherche doit être lisible par le navigateur des visiteurs, et versionné pour garder une trace de son évolution.

## Pourquoi il existe

Le moteur de recherche livré avec Ghost (`sodo-search`) n'indexe que le titre et l'extrait de chaque article — c'est écrit dans son code : `index: ['title', 'excerpt']`. Sur ce corpus, cela représente environ 154 000 signes indexés pour 4,4 millions publiés, soit 3,5 % du texte. Autrement dit : on retrouve un article dont on se souvient déjà du titre, pas un article dont on se souvient d'une idée.

Cet index-ci porte sur le texte intégral.

## Ce qu'il contient

| | |
|---|---|
| Articles indexés | 899 |
| Texte indexé | 4,4 M signes |
| Poids total | ~5,5 Mo, 980 fichiers |
| Téléchargé par recherche | ~170 ko (runtime + tranche d'index + fragments affichés) |

L'index est découpé en tranches : le navigateur ne récupère que celles qui concernent la requête, plus un fragment de 2,7 ko par résultat affiché.

Chaque entrée porte des métadonnées (titre, date, image, accès) et trois filtres : **pilier** (souveraineté, imprévisibilité, mobilité, factualité, solidarité — un article peut en porter plusieurs), **type** (article, newsletter, playground) et **année**.

Les articles réservés aux membres restent indexés sur leur titre et leur extrait, jamais sur leur corps : le Content API de Ghost ne délivre pas leur texte sans authentification.

## Comment il est construit

Par [`search_index_build.py`](https://github.com/davanac/FLTR) dans le dépôt FLTR : Content API Ghost (`formats=plaintext`) → enregistrements Pagefind → dossier `pagefind/`. La reconstruction est automatique et le résultat est poussé ici.

## Utilisation

```js
const pagefind = await import('https://davanac.github.io/fltr-search-index/pagefind/pagefind.js');
const résultats = await pagefind.search('souveraineté numérique');
```

## Miroir

Ce dépôt est également versionné sur [Codeberg](https://codeberg.org/davanac/fltr-search-index).
