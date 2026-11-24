# Déterminants de la nouvelle vague : des GJ à la GenZ
## Introduction
Où il est question de la topographie de la fin de l'époque contemporaine. Nous avons voulu analyser les déterminants socio-démographiques de la manifestation du 17 octobre. Nous nous sommes donc penchés sur les lieux d'action. Nous avons principalement produit des statistiques descriptives de l'endroit où elles se situent. Ensuite, nous avons donné quelques explications socio-démographiques. Et, enfin, nous avons décidé de questionner l'échelle. Nous avions les coordonnées précises du lieu d'action. Or, nous nous sommes vite aperçus que les individus pouvaient venir de différentes communes voire départements. Au lieu d'esquiver cette difficulté nous nous sommes penchés sur celle-ci.  

Pour le projet ont été utilisées les données suivantes 
- données scrapées sur un [site](https://www.17octobregiletjaune.net/carte/17-octobre/), créé par Benjamin Ball
- données topographiques fournies par etalab 
- elles sont stockées en S3.
· données recherchées sur le site data.economie.gouv.fr pour la fiscalité locale et les dépenses locales et la population 

## Organisation du projet 
Le gros du projet se trouve dans le notebook main.ipynb. Ensuite, ce notebook fait appel à plusieurs fonctions et codes présents dans les différents fichiers. 

```text
python_manifestation_explosion
├── bdd/                   # Données locales et fonction pour accéder au s3
├── useful/                # script avec les différentes fonctions pour la partie de statistique descriptive de la base principale 
├── modele_echelle/        # partie où l'on retrouve les fonctions qui ont permis l'analyse de l'impact des échelles sur l'étude
├── explications/          # partie où se trouvent différentes fonction pour l'analyse multivariée
├── main.ipynb             # notebook où l'on retrouve tous les résultats
├── requirements.txt       # Dépendances Python
└── README.md              # Readme d'explication du projet
```

## Limites des données
Les données ne correspondent qu'au 17 octobre. Il serait très intéressant de les comparer avec les autres jours de mobilisation voire d'autres mobilisations comme celles des gilets jaunes. 
Les données sont purement déclaratives ce qui pose un éventuel biais d'over ou d'underreporting. 
Les données ne donnent pas le nombre d'individus s'étant rendus aux différentes actions ce qui peut fausser la perception en fonction de la population des communes. Ce biais est légèrement corrigé par le type d'actions que l'on prend en compte. 

## Accéder et lancer le projet 
Normalement vous pouvez lancer le projet dans un terminal vscode ou jupyter 
git clone https://github.com/baptistekastler/python_manifestation_explosion.git
Au début de main, une commande permet d'installer les packages voulus pour faire tourner le code pip install 
Le code tourne avec les données qui se trouvent sur un bucket public donc vous pouvez faire tourner ce code. Sinon, veuillez contacter les auteur·ices. 

## Auteur·ices 
Nathalie Thai : nathalie.thai@enase.fr
Antoine Matos : antoine.matos@ensae.fr
Baptiste Kastler : baptiste.kastler@ensae.fr
