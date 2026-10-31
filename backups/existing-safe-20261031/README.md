# Existing safe helpers backup - 2026-10-31

This branch preserves four previously ignored helper scripts from the historical 1.0.17 release work. It does not change the application, production main, version, updater, manifests, OSS, website, or Release assets.

Baseline: `a142a7347115f71cd4a9d87e6da46214355a6148` in `nmrsz645-bit/shangchuanXtougao/main`. The complete Python application and current build scripts are already retained by that commit. Release `v1.0.17` remains fixed at `6071b4f6a640e3b27b78e302cff6a33fbeb57e6d`.

## Files and historical status

- `assemble_release.py`: historical 1.0.17 fresh-build assembler and archive audit. Current maintained packaging is `release/build_github_package.py`; this copy is archival.
- `verify_https_upgrade.py`: historical candidate/production HTTPS isolated old-install upgrade verification. It creates synthetic markers and invokes the updater in a new isolated installation. Backup only; it was not executed for this backup.
- `verify_isolated_upgrade.py`: historical loopback HTTP experiment. The updater requires HTTPS, so this is not the accepted production verification route. Preserve as an experiment; do not treat it as a passing test or fix.
- `verification/audit_packaged_code.py`: historical frozen-code/dependency inspection, including PE import inspection and generated version fixtures. It was not executed for this backup.

The first three snapshot copies replace the machine-specific dependency directory prefix with `C:\LOCAL_RELEASE_CANDIDATES\`. Original scripts are unchanged locally. Original and snapshot SHA256 values and replacement counts are recorded in MANIFEST.json. The audit script is byte-identical to the original. No credentials, business data, fixtures, reports, binaries, chat records, private project index, or private local HANDOFF are included.

## Recovery and dependencies

Retrieve this branch into a separate recovery directory. Read MANIFEST.json and verify SHA256SUMS.txt before selecting files. Preserve the historical relative layout shown in the manifest, use the baseline repository for imported project helpers, and explicitly supply clean old/new release fixtures. These archival paths and fixed 1.0.16/1.0.17 assumptions are not portable defaults. Do not overwrite an existing installation or run these scripts automatically.

Python 3.13.15 x64 and the exact dependency versions currently available on the backup machine are recorded in requirements.txt. They are a recovery reference, not proof that every historical run used the same environment. Most helpers use the Python standard library; the archive audit also imports PyInstaller and pefile. Official sources: https://www.python.org/downloads/windows/ , https://pypi.org/project/pyinstaller/6.22.2/ , https://pypi.org/project/pefile/2024.8.26/ . Existing product dependencies remain in the baseline requirements-build-windows.txt.

The original UpdateAgent project/source is still missing. The audited binary is already included in the existing GitHub program release; it is not duplicated here. No new tests, build, GUI, real upload, posting, or Feishu write was run.

## Backup scope and verification

MANIFEST.json records baseline, purpose, source/snapshot hashes and exclusions. SHA256SUMS.txt covers all snapshot files except itself. This snapshot is on an independent backup branch and is not merged into main. The commit uses [skip ci]; the repository has only an offline-test workflow, no Pages site, and no configured webhooks at the time checked. There is no production deployment in this backup.
