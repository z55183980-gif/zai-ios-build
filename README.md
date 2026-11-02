# Zai iOS builds

This public repository contains only the manual GitHub Actions build workflow.
Application source remains in the private `z55183980-gif/zai-ios` repository.
No source, application binaries, test bundles, signing files, or plain diagnostic
logs are published here. The public log reports stage results only. When a run
fails, its compiler and test logs are saved as an artifact encrypted to the
certificate in `DIAGNOSTICS_PUBLIC_CERT`, kept for one day.

Run **Build and upload TestFlight** on `main` with the full 40-character commit
SHA from the private source:

- `upload_testflight` off: compile and test only.
- `upload_testflight` on: compile, test, then sign and upload to TestFlight.
- `ui_preview` on: sign and upload at once, without tests. For checking how
  screens look. It compiles the application only and is not a release candidate.

Configure the protected `appstore` environment before running:

- Secrets: `SOURCE_DEPLOY_KEY`, `BUILD_CERTIFICATE_BASE64`, `P12_PASSWORD`,
  `BUILD_PROVISION_PROFILE_BASE64`, `KEYCHAIN_PASSWORD`,
  `APPSTORE_API_PRIVATE_KEY`.
- Variables: `IOS_TEAM_ID`, `APPSTORE_API_KEY_ID`, `APPSTORE_ISSUER_ID`,
  `DIAGNOSTICS_PUBLIC_CERT`, and optionally `IOS_MARKETING_VERSION` (defaults to
  `1.0`).

`SOURCE_DEPLOY_KEY` must be a read-only deploy key registered only on the private
source repository. The environment is restricted to the `main` branch. This
workflow has no push or pull request trigger, does not check out public
contributions, and grants no write permission to its GitHub token.

Build numbers start at `2.0.1`, above the private repository's 1.x series, and
increase with the workflow run number and attempt. Keep this repository's run
history; rebuilding an older run after publishing a newer run can produce an
obsolete build number.
