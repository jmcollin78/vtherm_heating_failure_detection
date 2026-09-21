# VTherm Heating Failure Detection

[Read this documentation in English](README.en.md)

Plugin Home Assistant de détection de panne de chauffage et de refroidissement pour [Versatile Thermostat](https://github.com/jmcollin/versatile_thermostat).

Il surveille la réponse de la température aux ordres produits par l'algorithme proportionnel du thermostat. En cas d'anomalie durable, il publie un événement compatible avec Versatile Thermostat et expose un capteur binaire utilisable dans les automatisations.

## Fonctionnement

Le plugin crée un gestionnaire `heating_failure_detection` pour chaque VTherm disposant d'une configuration effective.

- Une **panne de chauffage** est détectée lorsque la puissance demandée est supérieure ou égale au seuil de chauffage pendant le délai configuré, sans hausse de température suffisante.
- Une **panne de refroidissement** est détectée lorsque la puissance demandée est inférieure ou égale au seuil de refroidissement pendant le délai configuré, alors que la température continue d'augmenter.
- La détection est inactive lorsque le VTherm est arrêté, ne dispose pas d'algorithme proportionnel ou lorsque le template d'activation retourne une valeur fausse.
- Lorsqu'une vue de diagnostic des vannes est fournie par Versatile Thermostat, l'événement indique aussi une vanne potentiellement bloquée ouverte ou fermée.

Les seuils de puissance sont des fractions entre `0` et `1` : `0.80` correspond à `80 %`, `1.0` à `100 %`.

## Prérequis

- Home Assistant avec [Versatile Thermostat](https://github.com/jmcollin/versatile_thermostat) installé et configuré.
- Un VTherm utilisant un algorithme proportionnel.
- `vtherm_api` version `0.4.0` ou supérieure.

Le plugin dépend de l'intégration `versatile_thermostat` et ne commande aucun équipement : il observe l'état du VTherm et signale les anomalies.

## Installation

### Via HACS

[![Ouvrir ce dépôt dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jmcollin&repository=vtherm_heating_failure_detection&category=Integration)

1. Dans HACS, ajoutez ce dépôt comme intégration personnalisée.
2. Installez `VTherm Heating Failure Detection`.
3. Redémarrez Home Assistant.
4. Dans **Paramètres > Appareils et services > Ajouter une intégration**, ajoutez `VTherm Heating Failure Detection`.

### Installation manuelle

1. Copiez le dossier [custom_components/vtherm_heating_failure_detection](custom_components/vtherm_heating_failure_detection) dans le dossier `custom_components` de votre instance Home Assistant.
2. Redémarrez Home Assistant.
3. Ajoutez l'intégration `VTherm Heating Failure Detection` depuis **Paramètres > Appareils et services**.

## Configuration

La première entrée créée est l'entrée **globale** : elle définit les valeurs par défaut applicables à tous les VTherm. Ajoutez ensuite une nouvelle entrée de l'intégration et sélectionnez un thermostat pour créer une **surcharge ciblée**. Les valeurs de cette surcharge remplacent les valeurs globales pour ce seul VTherm.

| Option | Description | Valeur par défaut |
| --- | --- | --- |
| Activer la détection | Active ou désactive le gestionnaire de détection. | Activé |
| Seuil de chauffage | Puissance minimale à partir de laquelle une absence de montée en température est considérée. | `1.0` |
| Seuil de refroidissement | Puissance maximale sous laquelle une hausse de température peut indiquer une anomalie. | `0.0` |
| Variation minimale attendue | Hausse minimale de température attendue pendant le délai de détection. | `0.0` |
| Délai de détection | Durée, en minutes, pendant laquelle la condition doit persister. | `30` |
| Template d'activation | Template Home Assistant qui doit retourner `true`, `1`, `yes` ou `on` pour activer la détection. | Vide, donc actif |

Exemple de template pour ne surveiller que lorsque quelqu'un est présent :

```jinja
{{ is_state('person.alice', 'home') }}
```

Une erreur d'évaluation du template laisse volontairement la détection active, afin de ne pas masquer une panne.

Après toute création, modification ou suppression d'une entrée, seuls les VTherm concernés sont rechargés pour appliquer les nouveaux paramètres.

## Entités, attributs et événements

Pour chaque configuration ciblée, le plugin crée un capteur binaire dont l'identifiant unique reprend celui historique du VTherm :

```text
<vtherm_unique_id>_heating_failure_state
```

Le capteur est actif lorsqu'une panne de chauffage ou de refroidissement est détectée. Le climate VTherm conserve les attributs de suivi sous `heating_failure_detection_manager`, notamment les états individuels, seuils, délai et état du template.

À chaque début ou fin de panne, le plugin émet l'événement :

```text
versatile_thermostat_heating_failure_event
```

Le payload contient notamment `type`, `failure_type`, `on_percent`, `temperature_difference`, `current_temp`, `target_temp`, `threshold`, `detection_delay_min`, `is_enabled_by_template` et les champs de diagnostic `root_cause`.

Exemple d'automatisation qui notifie uniquement au début d'une panne de chauffage :

```yaml
alias: Alerte panne chauffage VTherm
triggers:
	- trigger: event
		event_type: versatile_thermostat_heating_failure_event
		event_data:
			type: heating_failure_start
			failure_type: heating
actions:
	- action: notify.mobile_app_mon_telephone
		data:
			message: >-
				Le chauffage ne produit pas la hausse de temperature attendue.
mode: single
```

## Limites

La détection signale une réponse thermique anormale ; elle ne peut pas confirmer seule l'origine d'une panne. Vérifiez les équipements, les capteurs de température, la consigne et les délais de chauffe avant toute intervention.

## Développement

Les tests unitaires du gestionnaire sont dans [tests/test_manager.py](tests/test_manager.py). Depuis un environnement contenant les dépendances Home Assistant :

```bash
pytest -q tests/test_manager.py
```
