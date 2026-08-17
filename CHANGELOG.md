# Changelog

## 1.5.0 - 2026-08-17

<!-- Release notes generated using configuration in .github/release.yml at master -->


**Full Changelog**: https://github.com/ocr99/ha-bicing/compare/v1.4.4...v1.5.0

## 1.4.4 - 2026-08-17

<!-- Release notes generated using configuration in .github/release.yml at master -->


**Full Changelog**: https://github.com/ocr99/ha-bicing/compare/v1.4.3...v1.4.4

## 1.4.3 - 2026-08-17

<!-- Release notes generated using configuration in .github/release.yml at master -->



**Full Changelog**: https://github.com/ocr99/ha-bicing/compare/v1.4.2...v1.4.3

## 1.4.2 - 2026-08-17

<!-- Release notes generated using configuration in .github/release.yml at master -->



**Full Changelog**: https://github.com/ocr99/ha-bicing/compare/v1.4.1...v1.4.2

## 1.4.1 - 2026-08-16

<!-- Release notes generated using configuration in .github/release.yml at master -->



**Full Changelog**: https://github.com/ocr99/ha-bicing/compare/v1.4.0...v1.4.1

## 1.4.0 - 2026-08-16

<!-- Release notes generated using configuration in .github/release.yml at master -->



**Full Changelog**: https://github.com/ocr99/ha-bicing/compare/v1.3.0...v1.4.0

## 1.2.0

- Afegits badges de validació, HACS, release i llicència al README.
- Afegida instal·lació directa mitjançant My Home Assistant.
- Afegit workflow de validació amb Hassfest i tests.
- Afegit workflow de release automàtica per tags `vX.Y.Z`.
- Afegides plantilles de contribució, seguretat, CODEOWNERS i bug reports.
- Millorada la metadata dels dispositius amb fabricant i model.
- Preparada la release 1.2.0.

## 1.1.0

- Reestructuració amb `DataUpdateCoordinator`, `runtime_data`, `coordinator.py` i `entity.py`.
- Evitades les peticions repetides d'informació per cada estació.
- El token deixa d'aparèixer als `options` i queda separat de la configuració de les estacions.
- Migració automàtica de config entries de versions anteriors.
- `unique_id` estable basat en l'ID de l'estació i la mètrica.
- Quatre sensors independents per estació.
- Dispositius de Home Assistant per estació.
- Entitats amb `has_entity_name` i traduccions.
- Millor classificació d'errors HTTP.
- Suport per a `429 Too Many Requests` i `Retry-After`.
- Cache d'últim estat amb disponibilitat basada en el coordinator.
- Reconfiguració sense update listener ni doble reload.
- Token de configuració amb selector de contrasenya.
- README ampliat i workflow de Hassfest.

## 1.0.0

- Primera versió publicada

## Origen del projecte

Aquest projecte és un **hard-fork** de [`oscarsanchezdm/bicing-hassio`](https://github.com/oscarsanchezdm/bicing-hassio), creat per **Òscar Sánchez de Mingo**.

## Canvis respecte al repositori original (oscarsanchezdm/bicing-hassio)

Fork personal amb correccions de seguretat, fiabilitat i bugs detectats en una
revisió de codi. Versió: `0.3.1` → `0.4.0`.

### Seguretat / fiabilitat

- **Detecció real d'errors d'autenticació (HTTP 401/403).** Abans només es
  detectava un token invàlid de forma indirecta (si l'API no responia amb
  `Content-Type: application/json`). Ara `BikeStationApi` distingeix
  explícitament un `401/403` (`BicingAuthError`) d'altres errors (`BicingApiError`),
  i tot i així es manté l'antiga heurística com a xarxa de seguretat.
- **Reautenticació automàtica durant el polling.** Abans, si el token
  caducava *després* de l'alta inicial de la integració, el sensor es
  quedava en estat `unknown` per sempre i mai es demanava un token nou. Ara
  el `DataUpdateCoordinator` llança `ConfigEntryAuthFailed`, cosa que fa
  aparèixer automàticament l'avís de "Cal tornar a autenticar-se" a HA.
- **El token ja no es guarda/proposa sense validar en el pas de reauth.**
  `async_step_token` ara valida el token nou contra l'API abans de desar-lo;
  si és invàlid, es mostra l'error al mateix formulari en lloc de desar un
  token trencat.
- **`diagnostics.py` nou, amb redacció del token** (`async_redact_data`).
  Si mai obres un issue i adjuntes el diagnòstic de la integració des de
  HA, el token surt automàticament ocultat.
- **Comprovació explícita del codi d'estat HTTP**, no només del
  `Content-Type`. Abans, una resposta d'error amb cos JSON (p. ex. un 403
  amb JSON) es colava i acabava petant amb un `KeyError` confús.

### Bug corregit (trencava la integració en HA recents)

- `config_flow.py` accedia al registre d'entitats amb
  `hass.helpers.entity_registry.async_get()`, un patró **deprecat i retirat
  progressivament** de Home Assistant Core. Es reemplaça per
  `entity_registry.async_get(hass)`, que és l'accés suportat actualment.
  Sense aquest fix, el pas "Reconfigurar" pot fallar amb `AttributeError`
  en versions recents de HA.

### Rendiment / bones pràctiques

- **Sessió HTTP compartida.** Abans es creava una `aiohttp.ClientSession`
  nova a cada crida (alta inicial, cada estació, cada cicle de polling).
  Ara totes les crides reutilitzen la sessió compartida de HA via
  `homeassistant.helpers.aiohttp_client.async_get_clientsession(hass)`,
  evitant handshakes TLS innecessaris cada 10 minuts.
- **`ConfigEntryNotReady` en comptes de `return False`** quan hi ha un
  error de xarxa a `async_setup_entry`, seguint el patró recomanat per HA
  perquè la integració es reintenti automàticament.
- **Backoff exponencial** simple als reintents de `get_stations_status`
  (abans era un `sleep(1)` fix).

### Bugs menors / neteja

- `strings.json` (idioma per defecte, anglès) definia camps
  `host`/`username`/`password` que no existeixen al formulari real (que
  només té `token`), i utilitzava claus `common::config_flow::abort::*`
  que **no existeixen** a Home Assistant per a `status_error`,
  `client_error`, `token_error` i `data_updated` — un usuari amb HA en
  anglès (o qualsevol idioma sense traducció pròpia) veia claus de
  traducció trencades en lloc de text llegible. Corregit amb text literal.
- `translations/ca.json` no tenia text per a `reauth_successful`,
  `cannot_connect`, `invalid_auth` ni `unknown`; completat.
- Eliminat l'`import *` de `.const` a `config_flow.py` (imports explícits).
- Eliminat codi mort a `async_update_token` (cridava
  `super().async_update_token(...)`, mètode que no existeix a la classe
  base `ConfigFlow`).
- Gestió d'excepcions més granular en el parseig JSON (`KeyError`/`TypeError`)
  per si l'API de dades obertes canvia lleugerament l'esquema.

### Pendent / idees per a més endavant

- Afegir tests automatitzats (`pytest-homeassistant-custom-component`).
- Considerar exposar un sensor "binary" (bicicletes/ancoratges disponibles
  sí/no) per a automatitzacions més simples.
