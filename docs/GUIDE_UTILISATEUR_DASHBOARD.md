# Guide utilisateur - Dashboard Ventes & Stocks

## Objectif

Ce guide explique comment utiliser le dashboard pour passer de la lecture des donnees a une decision metier actionnable.

Le parcours recommande suit 5 etapes:

1. Qualite des donnees
2. Detection des risques
3. Explication des alertes
4. Priorisation
5. Decision et export

## Acces

1. Lancer l'application Streamlit.
2. Ouvrir l'URL locale: `http://localhost:8501`.
3. Utiliser le menu lateral pour changer de page.

## Navigation des pages

Le dashboard contient 5 pages principales.

### 1) Chiffres cles

Usage:

- Voir les KPI globaux (CA, stocks, volumes, produits).
- Lire les graphiques de synthese.

Quand l'utiliser:

- Au debut pour prendre une photo rapide de la situation.

### 2) Tableau de bord decisionnel

Usage:

- Lire la matrice decisionnelle IA si disponible.
- Suivre les priorites: `Critique`, `A surveiller`, `Normal`.
- Analyser la decomposition du score et la lecture metier automatique des cas critiques.
- Consulter les actions prioritaires operationnelles.

Quand l'utiliser:

- Pour preparer la liste des actions a traiter.

### 3) Reporting qualite

Usage:

- Verifier les controles qualite (prix, SKU, id_web, Pandera).
- Utiliser le bouton `Sync quality exports depuis notebook` pour recharger les exports amont.
- Afficher les details techniques uniquement si necessaire via le toggle dedie.

Quand l'utiliser:

- Avant toute interpretation metier, pour valider la fiabilite du lot.

### 4) Veille metier & techno

Usage:

- Lire la synthese des choix methodologiques et technologiques du projet.

Quand l'utiliser:

- Pour justifier les decisions d'outillage et la trajectoire d'industrialisation.

### 5) Methodologie

Usage:

- Comprendre la logique globale du pipeline.
- Lire la definition du scoring et sa justification metier.

Quand l'utiliser:

- Pour expliquer le cadre de decision a un public non technique.

## Filtres (menu lateral)

Filtres disponibles:

- Disponibilite Web
- Categorie produit (si presente)
- Statut Stock (si present)
- Type de produit (si present)
- Plage de prix

Bonne pratique:

- Appliquer les filtres avant de lire les priorites, pour eviter une interpretation hors perimetre.

## Lecture metier du scoring decisionnel

Seuils utilises:

- `Critique`: `critical_score >= 0.65` (IF + SHAP + impact business, sans kNN/K-Means)
- `A surveiller`: `surveillance_score >= 0.45` (IF + kNN + K-Means + SHAP + impact business)
- `Normal`: sous les seuils de surveillance et de critique

Interpretation rapide:

- `Critique`: action sous 24-48h.
- `A surveiller`: controle hebdomadaire et suivi d'evolution, notamment pour les raretes kNN ou distances K-Means.
- `Normal`: surveillance standard.

## Exports disponibles

Depuis le dashboard:

- Reporting qualite (CSV)
- Matrice decisionnelle IA (CSV)
- Autres exports selon la page active

Usage recommande:

- Exporter apres application des filtres pour obtenir une liste d'action directement exploitable.

## Procedure type (10 minutes)

1. Ouvrir `Reporting qualite` et verifier le statut global.
2. Aller dans `Tableau de bord decisionnel`.
3. Filtrer le perimetre (web/categorie/prix) si besoin.
4. Traiter d'abord les `Critique`, puis les `A surveiller`.
5. Exporter la matrice pour suivi equipe.

## FAQ rapide

### Je ne vois pas la matrice decisionnelle IA

- Verifier que les exports BC05 sont presentes dans le dossier `data` du dashboard.
- Si necessaire, relancer la synchronisation des exports depuis le notebook.

### Je vois des alertes mais peu de cas critiques

- Normal: le scoring combine risque et impact business.
- Les cas `A surveiller` servent a prevenir une escalation future.

### Faut-il afficher les details techniques a tous les utilisateurs

- Non. Les details techniques sont optionnels.
- La lecture metier par priorite suffit pour la decision operationnelle.
