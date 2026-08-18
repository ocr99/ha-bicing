# Contributing

## Development

The integration is structured as a Home Assistant custom integration and uses a shared `DataUpdateCoordinator`.

Before opening a pull request:

1. Run the tests with `pytest -q`.
2. Make sure the Home Assistant Hassfest workflow passes.
3. Do not include API tokens, Home Assistant backups, `.storage` files, or other secrets in commits.

## Releases

The Home Assistant integration version is defined in
`custom_components/bicing/manifest.json`, but you should not edit it by
hand: releases are fully automated through the **Release** GitHub Actions
workflow.

1. Go to the repository's **Actions** tab → **Release** → **Run workflow**.
2. Optionally type an explicit version (e.g. `1.6.0`) in the **Release
   version** field.
   - Leave it **empty** to auto-bump the patch version instead
     (`X.Y.Z` → `X.Y.(Z+1)`).
3. Run the workflow.

The workflow itself, in order:

- Resolves the version (explicit input or auto patch bump) and validates
  it is not older than the current `manifest.json` version.
- Runs the test suite and Hassfest.
- Updates `custom_components/bicing/manifest.json` and commits it.
- Generates release notes from merged PRs and appends a matching section
  to `CHANGELOG.md`.
- Creates and pushes the `vX.Y.Z` tag.
- Publishes the GitHub Release.

Do not create tags or GitHub Releases manually — that would conflict with
what the workflow generates. HACS uses these GitHub releases/tags to
detect available integration updates.