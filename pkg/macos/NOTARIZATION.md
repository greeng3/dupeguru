# macOS code signing & notarization — setup guide

This is the complete, step-by-step procedure to make dupeGuru's macOS release
build **signed and notarized**, so macOS stops blocking it with
"dupeGuru can't be opened because the developer cannot be verified."

The CI plumbing already exists (`.github/workflows/release.yml`, the `macos`
job). It runs automatically **only when the six GitHub secrets below are
present**. Until then the build still succeeds but ships unsigned. Everything
left to do is listed here. None of it can be done for you — it involves your
Apple credentials and your GitHub repository settings.

> **Who does what:** You create the Apple certificate + API key and add the six
> secrets to GitHub (both require credentials nobody else should have). After
> that, the CI signs every release build with no further manual steps.

---

## 0. Prerequisites (one-time)

- An **Apple Developer Program** membership (paid, $99/yr).
- A Mac with **Keychain Access** (built in) and the **Xcode command line
  tools** (`xcode-select --install` if `xcrun` is missing — only needed if you
  ever want to test signing locally; CI already has them).
- Admin access to the GitHub repo **github.com/greeng3/dupeguru**.

You will produce **three Apple artifacts** (a certificate, an API key, your Team
ID) and turn them into **six GitHub repository secrets**.

---

## Part A — Create the Developer ID Application certificate

The certificate proves the app came from you. It **must** be the type
**"Developer ID Application"** (not "Apple Distribution", not "Mac App
Distribution" — those are for the Mac App Store, which is a different thing).

> This can only be created on the web portal, and only by the **Account Holder**
> of the Apple Developer account. On an individual account that is simply you.

### A.1 Generate a signing request (CSR) on your Mac

1. Open **Keychain Access** (Applications ▸ Utilities ▸ Keychain Access).
2. **Certificate Assistant is in the menu bar at the very top of the screen —
   not inside the Keychain Access window.** The window's sidebar only shows
   "My Certificates", "Keys", and "Certificates"; ignore those for this step.
3. First, click an **empty area** of the item list so that **nothing is
   selected**. (If a key or certificate is highlighted, the menu item in the
   next step renames itself to "…With \<that item\>" and does the wrong thing.)
4. In the menu bar at the top of the screen, open the **Keychain Access** menu
   (the one immediately right of the  Apple logo) ▸ **Certificate Assistant**
   ▸ **Request a Certificate From a Certificate Authority…**
5. Fill in:
   - **User Email Address:** your Apple ID email.
   - **Common Name:** anything recognizable, e.g. `dupeGuru Developer ID`.
   - **CA Email Address:** leave **blank**.
   - Select **Saved to disk** (not "Emailed to the CA").
6. Click **Continue** and save the file. You now have a
   `CertificateSigningRequest.certSigningRequest` file (the "CSR").

### A.2 Create the certificate on Apple's portal

1. Go to <https://developer.apple.com/account> and sign in.
2. Click **Certificates, Identifiers & Profiles**.
3. Select **Certificates** in the sidebar, then click the **＋** (Create a new
   certificate).
4. Under the **Software** section choose **Developer ID Application**. Click
   **Continue**.
   - If asked about the profile type / "G2 Sub-CA", accept the default
     (current/newest).
5. **Upload** the `.certSigningRequest` file from step A.1. Click **Continue**.
6. Click **Download**. You get a `developerID_application.cer` file.

> ⚠️ Apple caps you at **5 Developer ID certificates and they cannot be
> deleted.** Do not create throwaways. If you make a mistake, keep the extra and
> just use the good one.

### A.3 Install it and export a `.p12`

1. **Double-click** `developerID_application.cer`. It installs into your
   **login** keychain. (Keychain Access may open; that's fine.)
2. In Keychain Access, left sidebar: select the **login** keychain and the
   **My Certificates** category.
3. Find the entry named like **"Developer ID Application: Your Name
   (TEAMID)"**. Click the **disclosure triangle** on its left — you must see a
   **private key** nested underneath it. If there is no private key, the export
   will be useless (redo A.1–A.3 on the same Mac that generated the CSR).
4. Select **both** the certificate **and** its private key (Cmd-click both
   rows). Right-click ▸ **Export 2 items…**
5. Save as **Personal Information Exchange (.p12)**. Name it e.g. `dupeguru.p12`.
6. Set a **strong password** when prompted. **Write this password down** — it
   becomes the secret `MACOS_CERT_PASSWORD`.
   - macOS may also ask for your login/keychain password to allow the export;
     that's a different password and is not stored anywhere.

> 🔒 Anyone who has this `.p12` **and** its password can sign software as you.
> Treat it like a private key, because it contains one.

### A.4 base64-encode the `.p12`

GitHub secrets hold text, so the binary `.p12` must be base64-encoded. In
Terminal:

```sh
base64 -i dupeguru.p12 | pbcopy
```

This copies the encoded text to your clipboard. That text is the secret
`MACOS_CERT_P12_BASE64`. (Or write it to a file with
`base64 -i dupeguru.p12 -o dupeguru.p12.b64` and open that.)

---

## Part B — Create the App Store Connect API key (for notarization)

Notarization uploads the signed app to Apple's service for an automated malware
scan. The modern tool (`notarytool`) authenticates with an **App Store Connect
API key**. You need a **Team Key** — **individual keys do NOT work with
notarytool.**

### B.1 Open the keys page

1. Go to <https://appstoreconnect.apple.com> and sign in.
2. Click **Users and Access**.
3. Click the **Integrations** tab (top of the page).
4. In the sidebar, select **App Store Connect API**.
   - If you do **not** see this section, click **Request Access** once (only the
     Account Holder can) to enable the API for your account, then continue.
5. Make sure you are on **Team Keys** (the default), **not** "Individual Keys".

### B.2 Generate the key

1. Click **Generate API Key** (or the **＋**).
2. **Name:** something like `dupeguru-notarize`.
3. **Access:** choose **Developer**. (This role is sufficient for
   notarization.)
4. Click **Generate**.

### B.3 Capture the three values

1. **Download the key.** It's a file named `AuthKey_XXXXXXXXXX.p8`.
   **⚠️ You can download it only ONCE.** If you lose it, you must revoke the key
   and make a new one. Save it somewhere safe.
2. **Key ID:** the 10-character string shown in the key's row (also in the file
   name). This is the secret `AC_API_KEY_ID`.
3. **Issuer ID:** a UUID shown **above the list of keys** on this same page
   (looks like `57246542-96fe-1a63-e053-0824d011072a`). This is the secret
   `AC_API_ISSUER_ID`.

> Note: an API key's name and access level **cannot be edited** after creation.
> To change them you revoke and regenerate.

### B.4 base64-encode the `.p8`

```sh
base64 -i AuthKey_XXXXXXXXXX.p8 | pbcopy
```

That encoded text is the secret `AC_API_KEY_P8_BASE64`.

---

## Part C — Find your Team ID

1. Go to <https://developer.apple.com/account>.
2. Click **Membership details** (sometimes just "Membership").
3. Copy the **Team ID** — a 10-character alphanumeric string (e.g.
   `AB12CD34EF`). This is the secret `APPLE_TEAM_ID`.
   - It's also the parenthesized part of your certificate name from step A.3:
     "Developer ID Application: Your Name (**AB12CD34EF**)".

---

## Part D — Add the six secrets to GitHub

These are **GitHub Actions _repository_ secrets** — NOT "environment" secrets,
and nothing to do with Apple. The CI reads them at build time.

### Exact navigation

1. In a browser go to **<https://github.com/greeng3/dupeguru>**.
2. Click **Settings** (top tab of the repo; you must be the repo owner/admin).
3. In the left sidebar: **Secrets and variables** ▸ **Actions**.
4. You land on a page with tabs/sections. Use the **"Repository secrets"**
   section (the top one). **Do not** use "Environment secrets."
5. Click **New repository secret**, enter the **Name** and **Secret** value,
   click **Add secret**. Repeat for all six.

### The six secrets

| Secret name | Value comes from | What it is |
|---|---|---|
| `MACOS_CERT_P12_BASE64` | Part A.4 | base64 of your Developer ID `.p12` |
| `MACOS_CERT_PASSWORD` | Part A.3 step 6 | the password you set on the `.p12` |
| `APPLE_TEAM_ID` | Part C | your 10-char Team ID |
| `AC_API_KEY_ID` | Part B.3 | the API key's Key ID |
| `AC_API_ISSUER_ID` | Part B.3 | the Issuer ID (UUID) |
| `AC_API_KEY_P8_BASE64` | Part B.4 | base64 of the `.p8` key file |

> Names must match **exactly** (they're case-sensitive). A typo means the CI
> silently skips signing (it's gated on `MACOS_CERT_P12_BASE64` being present)
> or fails partway. Double-check spelling.

---

## Part E — Turn it on

1. **Merge PR #20** (<https://github.com/greeng3/dupeguru/pull/20>) into
   `master`. This adds the signing step and the entitlements file.
2. Trigger a build one of two ways:
   - **Test run:** GitHub ▸ **Actions** tab ▸ **Build Packages** workflow ▸
     **Run workflow** (this is `workflow_dispatch`). The artifact won't be a
     public Release, but it exercises the full sign + notarize path.
   - **Real release:** push a version tag (see the project's release process),
     which both builds and publishes a GitHub Release with the signed `.app`.
3. Watch the **macos** job. The **"Sign and notarize app bundle"** step should:
   - import the cert into a temporary keychain,
   - `codesign` the app,
   - `notarytool submit --wait` (this can take anywhere from ~1 to ~15 minutes
     while Apple scans it),
   - `stapler staple` the result.

### How to verify it worked

Download the resulting `dupeguru-macos.zip`, unzip, and run:

```sh
spctl -a -vvv -t install dupeguru.app
```

A notarized app reports **`source=Notarized Developer ID`** and
**`accepted`**. You can also confirm the staple with:

```sh
xcrun stapler validate dupeguru.app
```

---

## Troubleshooting / known gotchas

- **"No Developer ID Application identity found in keychain"** (CI fails in the
  sign step): the `.p12` didn't contain the private key, or
  `MACOS_CERT_P12_BASE64` / `MACOS_CERT_PASSWORD` is wrong. Re-export the `.p12`
  making sure **both** the cert and its key are selected (Part A.3), re-encode,
  re-add the secrets.
- **notarization status `Invalid`:** fetch the detailed log. Locally:
  `xcrun notarytool log <submission-id> --key … --key-id … --issuer …`. The most
  common cause for a PyInstaller/Python app is a hardened-runtime/entitlements
  issue — the entitlements live in `pkg/macos/entitlements.plist` and may need a
  tweak (e.g. add an allow-* key). This is the one place we may have to iterate
  after the first real run.
- **Individual API key error:** if notarytool rejects the credentials, confirm
  you created a **Team Key**, not an Individual Key (Part B.1 step 5).
- **The step didn't run at all:** it's gated on `MACOS_CERT_P12_BASE64` being
  present. If it's missing/misspelled, the whole signing step is skipped and the
  app ships unsigned.
- **Cert expired / renewed later:** Developer ID certs last ~5 years. On
  renewal, re-export the `.p12` and update `MACOS_CERT_P12_BASE64` (and the
  password secret if you change it).

---

## What this does NOT cover

- **Windows code signing** — a separate follow-up. Planned route is **Azure
  Trusted Signing** (~$10/mo; individual sign-up available in US/Canada).
  Reminder: no Windows option grants instant SmartScreen trust anymore;
  reputation builds over several signed releases.
- **The Mac App Store** — out of scope. Developer ID + notarization is for
  distributing the app yourself (direct download), which is what dupeGuru does.
