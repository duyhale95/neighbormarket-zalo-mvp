# Deplao compatibility gate — live sending currently blocked

The reviewed Deplao source is babyvibe/deplao-builder at
`2162f077d49f3b990121717fe6596fb3f0941e2f`. Its workflow engine can fall back
to another connected account when the selected account is missing. A workflow
`$pageId` check does not prevent this inside `getApi`. Therefore the stock
reviewed build is **not accepted for either live workflow**. No upstream checkout
or installed application has been modified by this integration.

The offline demo remains fully usable. Do not enable older generated workflows
or bypass the compatibility gate to demonstrate live delivery.

## Reviewable adapter prerequisite

`deplao-strict-account-binding.patch` is a small, unapplied MIT-attributed patch
for the reviewed engine. It removes the fallback and requires the requested
account's own connected API. It is provided for an operator to review in a
separate Deplao development checkout, build, and test. It is not proof that an
installed binary uses this source. Building or replacing the user's Deplao
application is outside the actions performed here.

After preserving local changes, an operator can check/apply the patch in that
separate checkout with `git apply --check <absolute-patch-path>` then
`git apply <absolute-patch-path>`. Follow that checkout's build instructions.
Do not apply it blindly to a different upstream version.

The generator checks the entire engine source, decoding UTF-8/BOM and normalizing
newlines. Accepted SHA-256 after this exact patch:
`e46f192bc6da62a2741d501c864f6d0f7f35168ea2e6bf9c8f895f25e4297705`.
Reviewed unpatched SHA-256:
`32cbe2568939e8aa57e004f22e5578d4c0a6630c74d5c93bafb35536184ebb07`.
Any other engine is refused until reviewed and tested; changing a hash to silence
the check is not validation.

```powershell
.\.venv\Scripts\python.exe -m tools.deplao_compat --source C:\path\to\reviewed-strict-deplao
```

This performs no login, send or source modification. The stock source deliberately
returns exit code 1. A pass only proves source compatibility.

## Installed-build and account checks (manual, still unverified)

1. Confirm that the exact reviewed patched source produced the application now
   running. Verify the node schemas against the installed version.
2. With a harmless controlled test workflow and the intended account
   disconnected, verify that the workflow fails instead of using a different
   connected account. Do not use real resident content for this check.
3. Bind exactly Meo Meo to both workflows. Confirm its own connection, private
   listener metadata, reply destination and authorized Legit group rights.
4. Only after these checks and the human review policy are validated, use both
   generator flags `--installed-build-verified --policy-validated`, plus
   `--deplao-source C:\path\to\reviewed-strict-deplao`. These flags record an
   operator attestation; they do not remotely inspect the application.
5. Follow the separate live evidence checklist in MENTOR_LIVE_DEMO.md. A mock
   receipt, passing graph test or source hash cannot complete a live checklist row.

## Other reviewed engine limits

- Send nodes interpret content starting with `[` as structured AI output,
  potentially including image URLs. Both normalized public posts and generated
  send messages now start with fixed plain text, keeping seller text as text.
- Rendered HTTP headers and PM snippets may enter Deplao's local execution logs.
  Protect those logs and credential-bearing exports; never publish them.
- A thrown send halts the graph. There is no invented error edge: the outbox
  lease expires to `unknown`. Stop/check the old publisher before reconciliation;
  never blindly send again after a timeout.
- This is a source-verified workflow subset, not an automated validation of the
  whole Deplao application. No supported strict runtime API has been assumed.

See THIRD_PARTY_NOTICES.md for Deplao's MIT notice and the mentor guide for the
fully offline fallback.
