# Windows code signing — setup guide (Azure Trusted Signing)

> **SUPERSEDED (2026-10-19).** The project moved off Azure (its Microsoft-login
> flow kept failing) to **Certum Open Source Code Signing** — see
> [`CERTUM_SIGNING.md`](CERTUM_SIGNING.md). This Azure guide is kept for
> reference only; the CI has not yet been reworked away from it.

This is the complete setup to make dupeGuru's Windows build **code-signed**, so
Windows SmartScreen stops showing the "Windows protected your PC / unknown
publisher" warning as the signing identity builds reputation over successive
releases.

We use **Azure Trusted Signing** (recently renamed *Azure Artifact Signing*):
Microsoft-run, cheap (~$10/mo), and it has a first-party GitHub Action. The CI
in `.github/workflows/release.yml` (the `windows` job) signs **both** the inner
PyInstaller `.exe` (so the installed app is signed) **and** the final NSIS
installer (the file users download). Signing runs **only when the Azure secrets
below are present**; until then the build still succeeds and ships an unsigned
installer.

> **Reality check:** No Windows option grants *instant* SmartScreen trust
> anymore (Microsoft removed that for EV certs in 2024). Trusted Signing builds
> **publisher reputation over several signed releases** — expect warnings to
> fade, not vanish on day one.

> **Who does what:** You create the Azure resources and add the six secrets.
> The signing is then automatic. None of this can be done for you — it's your
> Azure subscription and your GitHub secrets.

---

## 0. Prerequisites

- An **Azure subscription** (pay-as-you-go is fine). Create one at
  <https://portal.azure.com>.
- You must be in a supported region for individual validation (**USA or
  Canada** for individuals). You confirmed you qualify.
- Admin access to the GitHub repo **github.com/greeng3/dupeguru** to add
  secrets.

You will create: a **Trusted Signing account**, an **identity validation**, a
**certificate profile**, and a **service principal** with the signer role —
then turn those into **six GitHub repository secrets**.

> ⏳ **Start early:** the **identity validation** step is reviewed by Microsoft
> and can take anywhere from hours to several business days. Everything else is
> quick, but you're blocked on this, so kick it off first.

---

## Part A — Create the Trusted Signing account

1. In the [Azure portal](https://portal.azure.com), search for **Trusted
   Signing Accounts** (may appear as *Azure Artifact Signing*) and click
   **Create**.
2. Choose your subscription + a resource group (create one, e.g.
   `dupeguru-signing`).
3. Pick a **region** — remember it; it determines the signing **endpoint** URL
   (e.g. East US → `https://eus.codesigning.azure.net/`).
4. Give the account a **name** (e.g. `dupeguru`) — **case-sensitive**, you'll
   need it exactly later.
5. Create, and wait for deployment to finish.

Pricing: the **Basic** tier (~$9.99/mo, 5,000 signatures) is far more than a
release build needs.

---

## Part B — Validate your identity

1. In your Trusted Signing account, open **Identity validations** → **New
   identity validation**.
2. Choose **Individual** (or **Organization** if you prefer the publisher name
   to be an org). Fill in the details exactly as on your government ID.
3. Submit and **wait for approval** (this is the long pole). You'll get an
   approved validation you can attach to a certificate profile.

The name on the approved validation is the **publisher name** that will appear
on the signature, so use the name you want users to see.

---

## Part C — Create a certificate profile

1. In the account, open **Certificate profiles** → **Create**.
2. Profile type: **Public Trust** (this is what makes signatures trusted by
   Windows for distributed software).
3. Select the **approved identity validation** from Part B.
4. Give the profile a **name** (e.g. `dupeguru`) — **case-sensitive**, needed
   later.

---

## Part D — Create a service principal and grant it the signer role

CI authenticates as an Azure **app registration** (service principal) using a
client secret.

### D.1 App registration

1. Azure portal → **Microsoft Entra ID** → **App registrations** → **New
   registration**. Name it e.g. `dupeguru-ci-signing`. Register.
2. On its **Overview**, copy the **Application (client) ID** and the **Directory
   (tenant) ID**.

### D.2 Client secret

1. In the app registration → **Certificates & secrets** → **New client
   secret**. Set an expiry (note the date — you'll have to rotate it then).
2. **Copy the secret _Value_ immediately** (not the "Secret ID") — it's shown
   only once.

### D.3 Grant the signer role

1. Go to your **Trusted Signing account** → **Access control (IAM)** → **Add
   role assignment**.
2. Role: **Trusted Signing Certificate Profile Signer**.
3. Assign access to the **service principal** (`dupeguru-ci-signing`).
4. Save. Without this role you'll get **403** errors from the signing step.

---

## Part E — Gather the six values

| GitHub secret | Value |
|---|---|
| `AZURE_TENANT_ID` | Directory (tenant) ID (Part D.1) |
| `AZURE_CLIENT_ID` | Application (client) ID (Part D.1) — also the flag CI uses to detect that signing is configured |
| `AZURE_CLIENT_SECRET` | the client secret **Value** (Part D.2) |
| `AZURE_CODESIGN_ENDPOINT` | region endpoint, e.g. `https://eus.codesigning.azure.net/` (Part A.3) |
| `AZURE_CODESIGN_ACCOUNT` | Trusted Signing account name, exact case (Part A.4) |
| `AZURE_CODESIGN_PROFILE` | certificate profile name, exact case (Part C.4) |

---

## Part F — Add the six secrets to GitHub

These are **GitHub Actions _repository_ secrets** (not environment secrets).

1. **<https://github.com/greeng3/dupeguru>** → **Settings**.
2. Left sidebar: **Secrets and variables** → **Actions**.
3. Under **Repository secrets** → **New repository secret**. Add all six from
   the table above (names are case-sensitive).

CI gates signing on `AZURE_CLIENT_ID` being present: add all six, or signing is
skipped and the installer ships unsigned.

---

## Part G — Turn it on and verify

1. **Merge the Windows-signing PR** (the one that adds this file).
2. Trigger a build: **Actions** → **Build Packages** → **Run workflow**, or push
   a version tag.
3. Watch the **windows** job. With secrets present you'll see **Sign app
   binaries** and **Sign installer** run (they're skipped otherwise).

### Verify the downloaded installer is signed

On a Windows machine, right-click `dupeGuru_win64_<version>.exe` →
**Properties** → **Digital Signatures** tab → your publisher name should be
listed. Or in PowerShell:

```powershell
Get-AuthenticodeSignature .\dupeGuru_win64_<version>.exe | Format-List Status, SignerCertificate
```

`Status` should be **Valid**.

---

## How CI uses this (reference)

`package.py` was split so the Windows build runs in two stages
(`python package.py --stage build` then `--stage installer`), letting CI sign
the inner exe in between:

1. `--stage build` → PyInstaller → `dist/dupeguru-win64/`
2. **Sign app binaries** → Azure Trusted Signing over `dist/dupeguru-win64/*.exe`
3. `--stage installer` → NSIS → `dist/dupeGuru_win64_<version>.exe`
4. **Sign installer** → Azure Trusted Signing over `dist/*.exe` (top level only)

---

## Troubleshooting

- **403 from the signing step:** the service principal is missing the **Trusted
  Signing Certificate Profile Signer** role on the account (Part D.3), or the
  role hasn't propagated yet (wait a few minutes).
- **Endpoint/region mismatch:** `AZURE_CODESIGN_ENDPOINT` must match the region
  where the account/profile live (Part A.3).
- **Account/profile not found:** names are **case-sensitive** — copy them
  exactly as shown in the portal.
- **Auth fails:** confirm `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` /
  `AZURE_CLIENT_SECRET` are correct and the secret hasn't expired.
- **Signing step didn't run at all:** it's gated on `AZURE_CLIENT_ID`; a
  missing/misspelled secret skips signing and ships an unsigned installer.

### More secure auth (optional, later)

CI currently uses a client secret (simple, but a long-lived credential to
rotate). Microsoft recommends **OpenID Connect (federated credentials)**
instead — no stored secret. It needs a federated credential on the app
registration tying it to this GitHub repo, after which the three
`AZURE_*`-auth secrets can be dropped. Worth doing once the secret-based flow is
proven working.
