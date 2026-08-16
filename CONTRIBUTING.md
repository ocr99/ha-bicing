# Contributing

## Development

The integration is structured as a Home Assistant custom integration and uses a shared `DataUpdateCoordinator`.

Before opening a pull request:

1. Run the tests with `pytest -q`.
2. Make sure the Home Assistant Hassfest workflow passes.
3. Do not include API tokens, Home Assistant backups, `.storage` files, or other secrets in commits.

## Releases

The Home Assistant integration version is defined in `custom_components/bicing/manifest.json`.

1. Update the `version` field using semantic versioning.
2. Add a matching section to `CHANGELOG.md`.
3. Commit and push the changes.
4. Create and push a matching Git tag such as `v0.6.0`.

The release workflow validates the tag against `manifest.json` and creates the GitHub Release automatically. HACS uses GitHub releases/tags to detect available integration updates.
