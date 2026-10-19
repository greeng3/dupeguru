# Windows code signing — Certum Open Source Code Signing (step-by-step)

This is the complete walkthrough to make dupeGuru's Windows build **publicly
code-signed** using a **Certum Open Source Code Signing** certificate, so
Windows SmartScreen/UAC stop showing "unknown publisher" and the publisher
reputation builds over successive releases.

We chose this after dropping Azure Trusted Signing (its Microsoft-login flow
kept failing) and ruling out SignPath (not viable for a personal fork).

> **Set expectations up front.** No Windows option grants *instant* SmartScreen
> trust anymore — reputation builds as signed releases accumulate downloads.
> What a Certum cert buys you immediately is a **valid, publicly-trusted
> signature** (chains to a root already in Windows) and your name as the
> publisher, instead of "Unknown publisher." The publisher will read
> **"Open Source Developer &lt;Your Name&gt;"** (that's how Certum issues the OSS
> product).

---

## How this works (the 60-second mental model)

- The certificate is **cloud-based**: the private key lives on Certum's HSM and
  is accessed through their **SimplySign** service. You never hold a `.pfx` or a
  USB token. (This is mandatory — since 2023, publicly-trusted code-signing keys
  must live on certified hardware.)
- Normally you sign by running **SimplySign Desktop** on a PC and approving each
  session with the **SimplySign mobile app (2FA)**. That's interactive and does
  **not** work on an ephemeral GitHub-hosted runner.
- To sign **unattended in CI**, we use **[ssign](https://github.com/Le-Syl21/ssign)**
  — a small open-source CLI that talks to the SimplySign cloud over HTTPS (no
  desktop client, no PKCS#11) and Authenticode-signs **PE files** (`.exe`, `.dll`).
  dupeGuru's installer and inner executable are both PE files, so this fits.
- ssign authenticates with your **SimplySign email** + a **TOTP seed** (the
  secret behind the 2FA codes). So the one non-obvious prerequisite is:
  **capture that TOTP seed when you enroll** (see Part C) — if you only scan the
  2FA QR into your phone, you'll have to reset 2FA later to get it.

> ⚠️ **Honesty about the tooling.** Certum has *no official CI/CD API* (they've
> said it's "planned"). `ssign` is third-party and open-source, not vetted or
> supported by Certum. It works and is widely used, but you're trusting
> community code with signing access. If you'd rather not, see
> **Alternative: local signing** at the end — you sign on your own Windows
> machine with the mobile app, and never put a signing credential in CI.

---

## Who does what (summary)

| # | Step | Where | Done by |
|---|------|-------|---------|
| A | Buy the Open Source cert | Certum store | **You** |
| B | Identity validation | Certum (+ your ID) | **You** |
| C | Enroll on SimplySign **and capture the TOTP seed** | Certum / your phone | **You** |
| D | Collect the 3 CI inputs (email, TOTP seed, thumbprint) | your notes | **You** |
| E | Add the GitHub repository secrets | GitHub | **You** (only you can) |
| F | Rework the CI to sign with ssign | `release.yml` / `package.py` | **Claude** (a PR you merge) |
| G | Cut a release and verify the signature | GitHub + a Windows PC | **You** (Claude can trigger/inspect the run) |

Nothing in A–E can be done by Claude — they need your identity, your purchase,
your phone, and your repo-secrets access. Claude does F (the code) and can help
drive/verify G.

---

## Part A — Buy the Open Source Code Signing certificate

1. Go to the Certum store's **[Open Source Code Signing on SimplySign](https://shop.certum.eu/open-source-code-signing-on-simplysign.html)**
   product (also mirrored at [certum.store](https://certum.store/open-source-code-signing-on-simplysign.html)).
   - Price is roughly **$58–70 / €49+ per year** (confirm at checkout; cheaper
     than the standard individual cert, which is ~$99+).
   - Make sure it's the **"Open Source"** product on **SimplySign (cloud)** —
     not the standard/EV product, and not a USB-token variant.
2. Create a Certum account and complete the purchase. You'll get access to the
   **Certum / SimplySign** dashboard where the certificate request lives.

> **Validity note:** since Feb 27, 2026 a single code-signing certificate can
> last at most **459 days**; multi-year orders include free reissues. Plan to
> rotate the CI secrets when you reissue (Part E).

---

## Part B — Identity validation

Certum must verify (a) **who you are** and (b) that you're an **open-source
developer**, before it issues the cert.

1. In the Certum dashboard, start the certificate's **verification / data
   confirmation** step.
2. Provide the identity documents Certum asks for. Depending on country and
   method this is usually one of:
   - a government photo ID (passport / national ID) plus a selfie/video check, or
   - verification through an electronic identity scheme, or
   - a notarized document.
   Follow whichever method the dashboard offers you.
3. For the "open source" qualification, be ready to point at the project —
   dupeGuru is **GPLv3** (OSI-approved), and your fork is public at
   `github.com/greeng3/dupeguru`. If they ask for a reference to your work, that
   repo is it.
4. **Wait for approval.** This is reviewed by humans and can take anywhere from
   a day to a couple of weeks depending on the method and backlog. This is the
   long pole — start it early; everything else is quick.

The approved name becomes the publisher on your signatures (prefixed with
"Open Source Developer").

---

## Part C — Enroll the certificate on SimplySign, and CAPTURE THE TOTP SEED

This is the step people get wrong, because the thing CI needs (the TOTP seed) is
only shown **once**, during 2FA setup.

1. Once the cert is approved, Certum walks you through **activating it on
   SimplySign** (binding the issued certificate to your SimplySign cloud
   account). Install the **SimplySign mobile app** if prompted.
2. During activation you set up **two-factor authentication (TOTP)**. You'll be
   shown a **QR code and/or a text secret key** (a ~16–32 character Base32
   string).
   - **Do not just scan the QR with your phone and move on.**
   - **Copy and save the text secret key** somewhere safe (a password manager).
     *That* string is the **TOTP seed** CI needs. If the screen only shows a QR,
     use the app's "manual entry / can't scan" option to reveal the text secret,
     and save it.
   - Still scan it into your phone too (you'll use the phone for any interactive
     signing).
3. Finish activation and confirm you can generate 6-digit codes (phone shows
   them; the saved seed produces the same codes).

> 🔒 **The TOTP seed is a signing credential.** Anyone who has your SimplySign
> email **and** this seed can sign software as you, for the life of the
> certificate. Treat it like a private key. If you ever can't retrieve it, you
> can reset 2FA in SimplySign and set it up again (re-capturing the seed).

---

## Part D — Collect the three things CI needs

Write these down (you'll paste them into GitHub in Part E):

1. **SimplySign email** — the account/login email for SimplySign.
2. **TOTP seed** — the Base32 secret from Part C.
3. **Certificate thumbprint (SHA-1)** — a 40-character hex string identifying
   *which* cert to sign with. Get it one of these ways:
   - In **SimplySign Desktop** → certificate details → "Thumbprint"/"Odcisk", or
   - from the issued certificate's properties in the Certum dashboard, or
   - on a Windows PC with the cert loaded: `certutil -store -user My` and read
     the `Cert Hash(sha1)` line.
   Remove any spaces so it's a continuous 40-char string.

(ssign for PE files can often select the cert automatically if your account has
one signing cert, but having the thumbprint makes the CI unambiguous and is good
to have on hand.)

---

## Part E — Add the GitHub repository secrets

These go in **GitHub Actions _repository_ secrets** (not environment secrets),
and only you can add them.

1. Browser → **<https://github.com/greeng3/dupeguru>** → **Settings**.
2. Left sidebar → **Secrets and variables** → **Actions**.
3. Under **Repository secrets** → **New repository secret**. Add:

| Secret name | Value (from Part D) |
|---|---|
| `CERTUM_EMAIL` | your SimplySign email |
| `CERTUM_TOTP_SEED` | the Base32 TOTP seed |
| `CERTUM_CERT_SHA1` | the 40-char certificate thumbprint |

(Exact names are a convention Claude will match in the CI PR — if you prefer
different names, say so before Part F.)

> **Security tradeoff, stated plainly:** these secrets let the CI (and anyone
> who can exfiltrate them, e.g. via a malicious workflow change) sign as you.
> Mitigations Claude will build in / you can enable: gate signing on a
> **protected GitHub Environment** with required reviewers, restrict who can
> edit workflows, and rotate the seed when you reissue the cert. If this risk
> isn't acceptable, use **local signing** (end of doc) instead of CI secrets.

---

## Part F — CI rework (Claude does this as a PR you merge)

The current `release.yml` is wired for **Azure** Trusted Signing. Claude will
replace that with Certum/ssign. The good news: the hard part — splitting the
Windows build so the inner exe is signed *before* NSIS wraps it — is **already
done** (`package.py --stage build|installer`, from the earlier Windows work).
Only the signing *steps* change.

What the reworked `windows` job will do (all gated on the Certum secrets being
present, so builds without them still succeed unsigned):

1. `python package.py --stage build` → PyInstaller → `dist/dupeguru-win64/`
2. **Install ssign** (pinned version).
3. **Sign the inner exe**: `dist/dupeguru-win64/dupeguru-win64.exe` via ssign,
   authenticating with `CERTUM_EMAIL` + a one-time code generated from
   `CERTUM_TOTP_SEED`, selecting `CERTUM_CERT_SHA1`, timestamping against
   Certum's RFC-3161 server `http://time.certum.pl`.
4. `python package.py --stage installer` → NSIS → `dist/dupeGuru_win64_<ver>.exe`
5. **Sign the installer** the same way.
6. Upload.

Illustrative shape of the signing step (exact ssign flags are pinned to its
README when Claude writes the PR — treat this as the idea, not the final text):

```yaml
- name: Sign (Certum via ssign)
  if: env.CERTUM_EMAIL != ''
  env:
    SSIGN_EMAIL:     ${{ secrets.CERTUM_EMAIL }}
    SSIGN_OTP_SEED:  ${{ secrets.CERTUM_TOTP_SEED }}
    SSIGN_CERT_SHA1: ${{ secrets.CERTUM_CERT_SHA1 }}
  run: |
    ssign sign --sha1 "$SSIGN_CERT_SHA1" \
      --timestamp http://time.certum.pl \
      dist/dupeguru-win64/dupeguru-win64.exe
```

> **Expect one round of iteration on the first real run.** Because Certum has no
> official CI path and we're driving a third-party tool against a live 2FA
> service, the first tagged build after you add the secrets may need a tweak
> (code generation timing, cert selection, ARM-vs-x64 signtool quirks). Claude
> can't fully validate this without your live secrets, exactly like the macOS
> signing bring-up.

When you've finished Parts A–E, tell Claude "do the Certum CI PR" and it will
open it (you merge, as always).

---

## Part G — Cut a release and verify

1. Merge the CI PR (Part F), make sure the three secrets are set.
2. Cut a release tag as usual (`git tag -a vX.Y.Z … && git push origin vX.Y.Z`),
   or run **Actions → Build Packages → Run workflow** to test without publishing.
3. Watch the **windows** job — with secrets present the **Sign** steps run
   (skipped otherwise).
4. **Verify on a Windows PC.** Download `dupeGuru_win64_<ver>.exe`, then:
   - Right-click → **Properties → Digital Signatures** → you should see
     **"Open Source Developer &lt;Your Name&gt;"**, or
   - PowerShell:
     ```powershell
     Get-AuthenticodeSignature .\dupeGuru_win64_<ver>.exe | Format-List Status, SignerCertificate
     ```
     `Status` should be **Valid**.
   - The installed `dupeguru-win64.exe` should also be signed (that's why we sign
     the inner exe before NSIS).

SmartScreen may still show a (milder) "unrecognized app" warning on first
downloads until reputation accrues — that's expected and fades with release
volume.

---

## Troubleshooting

- **ssign auth fails / bad OTP:** the TOTP seed is wrong, or the generated code
  expired. Confirm the seed matches the codes your phone shows. Codes rotate
  every 30s; CI must generate a fresh one at sign time.
- **"certificate not found":** `CERTUM_CERT_SHA1` doesn't match a cert on the
  account, or has stray spaces. Re-copy it (Part D).
- **Signing step skipped:** it's gated on `CERTUM_EMAIL`; a missing/misspelled
  secret skips signing and ships an unsigned installer.
- **Timestamp errors:** Certum's TSA is `http://time.certum.pl`; transient
  failures happen — a re-run usually clears them. Always timestamp, so
  signatures stay valid after the cert expires.
- **Monthly signature cap:** SimplySign cloud allows ~5,000 signatures/month —
  far more than releases need.
- **Cert reissue/rotation:** when Certum reissues (≤459-day limit), the
  thumbprint changes — update `CERTUM_CERT_SHA1` (and the seed if 2FA was reset).

---

## Alternative: local signing (no signing credential in CI)

If putting the TOTP seed in CI secrets isn't acceptable, sign **on your own
Windows machine** instead:

1. Build the release artifacts (CI produces the **unsigned** installer, or build
   locally).
2. Run **SimplySign Desktop**, log in, approve the session with the **mobile
   app**.
3. Sign the inner exe and the installer with `signtool` (or ssign) using the
   cert thumbprint and `http://time.certum.pl`.
4. Upload the signed installer to the GitHub Release manually.

This keeps the signing credential entirely on your machine + phone (nothing in
CI), at the cost of a manual step each release. It's the most conservative
option and still produces the same publicly-trusted signature.

---

## Sources

- Certum Open Source product: <https://shop.certum.eu/open-source-code-signing-on-simplysign.html>
- Certum "Code Signing in the Cloud" manual (signtool/jarsigner): <https://files.certum.eu/documents/manual_en/CS-Code_Signing_in_the_Cloud_Signtool_jarsigner_signing.pdf>
- ssign (headless SimplySign signer, PE files, pure HTTPS): <https://github.com/Le-Syl21/ssign>
- Alternative community GitHub Action (SimplySign Desktop + signtool): <https://github.com/jay0lee/certum-cloud-code-sign>
