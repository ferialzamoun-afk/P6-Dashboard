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
- kNN est utilise comme score non supervise de rarete locale : il n'apprend pas une cible metier, il repere les produits statistiquement isoles dans leur voisinage.

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

## Point de vigilance sur les compteurs critiques

Le nombre de produits critiques peut augmenter lorsque le score decisionnel integre kNN et K-Means, car ces signaux valorisent la rarete statistique et la distance au profil de cluster. Ce n'est pas une derive aleatoire du kNN : le calcul est deterministe a donnees et seuils constants. L'ecart vient du choix de ponderation et des seuils appliques au score composite.

Pour obtenir une liste critique plus stricte, trois remediations sont possibles :

- reserver kNN au niveau `A surveiller` et non au passage direct en `Critique` ;
- plafonner la contribution kNN dans le score critique ;
- definir `Critique` uniquement avec une regle combinee : atypie IF forte + impact business ou anomalie metier confirmee.

La lecture recommandee est donc : kNN aide a prioriser les investigations, tandis que la decision critique doit rester validee par des signaux metier actionnables.

## Regle retenue dans le dashboard

La matrice decisionnelle distingue maintenant deux scores :

- `surveillance_score` : score large incluant IF, kNN, K-Means, SHAP et impact business. Il sert a alimenter la file `A surveiller`.
- `critical_score` : score strict limite a IF, SHAP et impact business. Il sert a declencher `Critique`.

Cette separation permet de conserver la valeur exploratoire du kNN et de K-Means sans transformer une simple rarete statistique en urgence metier. Sur les filtres courants du tableau de bord decisionnel, cette regle ramene la liste critique a une short-list stricte, tout en conservant les produits rares dans `A surveiller`.

## Reference

- Ce document est la version locale de la veille metier du dashboard.
- La synthese complete du projet reste dans la documentation P13.