# Streamlit ↔️ Google Sheets Starter

A tiny, deploy-ready Streamlit app that reads from (and appends to) a Google Sheet using a **service account**.

## 📦 What's inside

```text
streamlit-sheets-starter/
├─ app.py
├─ requirements.txt
├─ README.md
├─ LICENSE
└─ .streamlit/
   └─ secrets.toml.example
```

## 🚀 Quick start (local)

1. Create a Google **Service Account** in Google Cloud and download the JSON.
2. Share your Google Sheet with the service account **client_email** (Editor access).
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in values.
4. Install deps & run:
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```

## ☁️ Deploy to Streamlit Cloud

1. Push this repo to GitHub.
2. Create a new Streamlit app from the repo.
3. In **Settings → Secrets**, paste the contents of your `secrets.toml` (same format as the example).
4. Deploy.

## 🔐 `secrets.toml` format

```toml
# Top-level app settings
sheet_id = "YOUR_SHEET_ID_HERE"
worksheet_name = "Sheet1"

# Your service account JSON as TOML entries
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# Keep the \n newlines in the private_key exactly like this:
private_key = "-----BEGIN PRIVATE KEY-----\nABCDEF...\n-----END PRIVATE KEY-----\n"
client_email = "your-sa@your-project-id.iam.gserviceaccount.com"
client_id = "1234567890"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/your-sa%40your-project-id.iam.gserviceaccount.com"
universe_domain = "googleapis.com"
```

> **Note:** In the Google Sheet, click **Share** → add the **service account email** with **Editor** permissions.

## 🧰 Common issues

- **No secrets files found** (locally): ensure the file is at `.streamlit/secrets.toml` before `streamlit run`.
- **Worksheet not found**: the `worksheet_name` must match the tab name in your sheet.
- **Private key formatting**: preserve `\n` line breaks inside `private_key` if using single-line TOML.

## 🪪 License
MIT
