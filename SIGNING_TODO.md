# SIGNING_TODO — publishing a signed Elysium 1.3.0

Today the update server tells the truth by *omitting* download URLs: both
`/poamforge/latest.json` (frozen at the last released **1.2.5**) and
`/elysium/latest.json` (**1.3.0**, `prerelease: true`) describe a release but
carry **no `url`**, because no signed installer is hosted. The Elysium client's
`PlatformEntry.url` is `Option<String>`, so an absent url deserializes to `None`
and `download_url` becomes an empty string — nothing 404s and no installer is
offered (see `elysium: source/src-tauri/src/updater.rs`).

Blocked on **biz-1** (the Sectigo EV code-signing certificate). Do **not** add a
`url` or set `signed: true` until a signed artifact is actually hosted and
`curl -I <url>` returns **HTTP 200** — the `Manifest check` workflow
(`.github/workflows/manifest-check.yml`) enforces exactly that and will turn the
build red otherwise.

## When a signed, hosted 1.3.0 exists, make these exact edits

### 1. `elysium/latest.json`
- Add `"url"` to `platforms."windows-x86_64"`, pointing at the hosted signed MSI,
  e.g. `"https://updates.animusai.net/elysium/Elysium_1.3.0_x64_en-US.msi"`
  (must return 200).
- Set `"signed": true`.
- Set `"prerelease": false` (or remove the `prerelease` key).
- Remove the top-level `"note": "unsigned build; download available after code-signing"`.
- Update `platforms."windows-x86_64".sha256` and `size` to the **signed**
  artifact's values (signing changes the bytes, so the current unsigned
  `sha256`/`size` will no longer match), and drop or rewrite the platform-entry
  `note` that explains the missing url.

### 2. `poamforge/latest.json`
- Bump `"version"` from `1.2.5` to `1.3.0` **only once the signed 1.3.0 is the
  build you want pinned clients to move to** (this is a rename-successor path; the
  `successor` key already points clients at `/elysium/latest.json`).
- If you want pinned `/poamforge/` clients to be able to download directly, add
  the same signed `"url"` (200-checked) and set `"signed": true`; otherwise leave
  the url omitted and rely on `successor`.
- Update `sha256`/`size`/`filename` to match the signed 1.3.0 artifact, and drop
  the platform-entry `note` about the missing url.

### 3. Verify before merge
- `curl -I` every new url and confirm **200** (the CI does this too).
- Confirm each manifest still parses against
  `schema/server-manifest.schema.json`.
- After merge, `curl` the live Pages paths:
  - `https://updates.animusai.net/poamforge/latest.json`
  - `https://updates.animusai.net/elysium/latest.json`

Until all of that holds, the honest state is the current one: describe the
release, omit the url.
