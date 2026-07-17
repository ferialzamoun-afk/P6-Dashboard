# Veille metier et technologique du projet

## Objectif

Donner une lecture metier des choix techniques utilises dans le dashboard pour la qualite, la detection et la priorisation.

## Ligne directrice

- Detecter les cas a risque.
- Expliquer les alertes.
- Prioriser les actions.
- Decider avec un export exploitable.

## Choix retenus

### Qualite

- Pandera pour les controles amont sur les donnees critiques.
- Regles metier pour bloquer les incoherences de base.

### Detection

- Z-score/IQR pour les cas simples et rapides a verifier.
- Isolation Forest pour la detection multivariee des anomalies.

### Priorisation

- SHAP pour expliquer les alertes et rendre la decision actionnable.
- K-Means et kNN pour ordonner les investigations en second niveau.

## Pourquoi ces choix

- Ils restent lisibles pour un utilisateur metier.
- Ils ajoutent peu de complexite au dashboard.
- Ils permettent une lecture progressive: controle, alerte, explication, priorisation.

## Articulation avec la gouvernance qualite

- Pandera bloque les erreurs de donnees en amont du scoring.
- Great Expectations peut prendre le relais en aval pour la publication et la traçabilite.

## Impact attendu

- Moins d'alertes non interpretables.
- Priorisation plus claire des produits a traiter.
- Meilleure cohesion entre dashboard, notebook et documentation projet.

## Reference

- Ce document est la version locale de la veille metier du dashboard.
- La synthese complete du projet reste dans la documentation P13.