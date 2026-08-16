# Bicing per al Home Assistant

[![Validate](https://github.com/ocr99/ha-bicing/actions/workflows/validate.yml/badge.svg)](https://github.com/ocr99/ha-bicing/actions/workflows/validate.yml)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://www.hacs.xyz/)
[![Latest Release](https://img.shields.io/github/v/release/ocr99/ha-bicing?sort=semver)](https://github.com/ocr99/ha-bicing/releases)
[![License](https://img.shields.io/github/license/ocr99/ha-bicing)](https://github.com/ocr99/ha-bicing/blob/master/LICENSE)

Integració per a Home Assistant que mostra l'estat de les estacions del Bicing de Barcelona mitjançant els datasets de dades obertes de l'Ajuntament de Barcelona.

## Funcionalitats

- Configuració completa des de la interfície de Home Assistant.
- Selecció de les estacions que vols monitoritzar.
- Quatre sensors independents per estació:
  - Bicicletes disponibles.
  - Bicicletes elèctriques disponibles.
  - Bicicletes mecàniques disponibles.
  - Ancoratges disponibles.
- Cada estació es representa com un dispositiu de Home Assistant.
- Actualització coordinada cada 10 minuts.
- Una sola petició de dades d'estat per actualització, independentment del nombre d'estacions configurades.
- Reutilització de la sessió HTTP de Home Assistant.
- Cache de l'últim estat durant errors transitoris durant un màxim d'1 hora.
- Reautenticació automàtica des de la interfície quan el token és rebutjat.
- Gestió de `429 Too Many Requests` i `Retry-After`.
- Diagnòstics amb el token redactat.
- Migració automàtica de la configuració de versions anteriors.

## Instal·lació amb HACS

### Instal·lació directa

[![Obre Bicing a HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ocr99&repository=ha-bicing&category=integration)

Prem el botó anterior des del mateix dispositiu on tens Home Assistant o afegeix manualment el repositori `ocr99/ha-bicing` a HACS com a repositori personalitzat de tipus **Integration**.

### Instal·lació manual

Copia la carpeta `custom_components/bicing` dins de `config/custom_components/bicing` i reinicia Home Assistant.

Després ves a **Configuració → Dispositius i serveis → Afegeix integració** i busca **Bicing Status**.

## Configuració

Necessitaràs un token del servei de dades obertes de l'Ajuntament de Barcelona. El pots obtenir gratuïtament a:

https://opendata-ajuntament.barcelona.cat/tokens

Després, a Home Assistant:

1. Ves a **Configuració → Dispositius i serveis**.
2. Afegeix la integració **Bicing Status**.
3. Introdueix el token.
4. Selecciona les estacions que vols monitoritzar.

Les estacions es poden modificar posteriorment des de **Reconfigurar** a la fitxa de la integració.

## Actualitzacions

Les noves versions es publiquen com a releases de GitHub i HACS les detecta com a actualitzacions disponibles. Per als usuaris que instal·len la integració amb HACS, no cal copiar manualment els fitxers de cada nova versió.

La release es crea des de **GitHub → Actions → Release → Run workflow**. Només cal introduir la versió, per exemple `1.3.0`.

El workflow:
1. Actualitza automàticament `custom_components/bicing/manifest.json`.
2. Executa els tests i Hassfest.
3. Fa el commit de la nova versió.
4. Crea i puja el tag `v1.3.0`.
5. Crea la GitHub Release amb generated notes.

No cal editar manualment la versió del `manifest.json` ni crear la tag a mà.

## Entitats

Cada estació seleccionada es representa com un dispositiu de Home Assistant amb aquestes entitats:

- `Bicicletes disponibles`: suma de bicicletes mecàniques i elèctriques.
- `Bicicletes elèctriques disponibles`.
- `Bicicletes mecàniques disponibles`.
- `Ancoratges disponibles`.

Això permet crear gràfics i automatitzacions sobre cada mètrica per separat.

## Actualització i errors

L'estat es consulta cada 10 minuts. Si l'API falla temporalment, la integració conserva l'últim valor conegut durant un màxim d'una hora. Quan aquest període expira, les entitats passen a **unavailable** fins que l'API torna a respondre correctament.

Els errors HTTP 401/403 provoquen el flux de reautenticació. Els errors 429 i els errors temporals del servidor respecten el mecanisme de reintent quan l'API proporciona `Retry-After`.

## Privacitat i secrets

El token de l'API només es guarda a la configuració de Home Assistant i no forma part del repositori. Els diagnòstics de la integració redacten el token abans de retornar informació.

No comparteixis mai un fitxer de backup de Home Assistant o el contingut de `.storage/core.config_entries` si conté el token.

## Origen de les dades

- [Informació de les estacions del Bicing](https://opendata-ajuntament.barcelona.cat/data/ca/dataset/informacio-estacions-bicing)
- [Estat de les estacions del Bicing](https://opendata-ajuntament.barcelona.cat/data/ca/dataset/estat-estacions-bicing)

![Notificació](images/notification.png)

## Desenvolupament

La integració utilitza un `DataUpdateCoordinator` compartit per totes les entitats de Bicing. La informació estàtica de les estacions es carrega una sola vegada durant la inicialització i l'estat es consulta en bloc.

Per validar els canvis localment:

```bash
python -m pip install --upgrade pip pytest pytest-homeassistant-custom-component
pytest -q
```

Abans d'obrir un issue, comprova els logs de Home Assistant i, quan sigui possible, adjunta els diagnòstics de la integració sense compartir mai el token.

## Eliminació

Per eliminar la integració, ves a **Configuració → Dispositius i serveis → Bicing Status → ... → Elimina**.

Això eliminarà la configuració i les entitats associades a la integració.

## Llicència

Aquest projecte es distribueix sota la llicència MIT.
