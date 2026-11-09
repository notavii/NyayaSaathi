# NYAYA SAATHI (न्याय साथी) — DEPLOYMENT GUIDE
## Target: Streamlit Community Cloud (100% Free Hosting)

This guide provides step-by-step instructions to publish **Nyaya Saathi** to your GitHub repository and deploy it to **Streamlit Community Cloud** with zero hosting costs.

---

## 1. Prerequisites Checklist

Before you begin, ensure you have:
1. **GitHub Account**: Signed up at [github.com](https://github.com).
2. **Streamlit Community Cloud Account**: Signed up at [share.streamlit.io](https://share.streamlit.io) (sign in using your GitHub account for seamless 1-click authorization).
3. **Google AI Studio API Key**: A free Gemini API key from [aistudio.google.com](https://aistudio.google.com).

---

## 2. Publish Project to GitHub

The repository is already fully configured locally with `.gitignore` and portable paths.

> [!IMPORTANT]
> **Privacy & Secret Protection**:
> `.gitignore` is strictly configured to protect your credentials. Your local `.env` and `.streamlit/secrets.toml` files will **never** be committed to GitHub.
> The prebuilt vector database (`data/legal_sources/chroma_db/`, 14 MB total) **is included** so that Streamlit Cloud will launch instantaneously without needing to re-index the legal corpus.

### Option A: Using Command Prompt / PowerShell (Recommended)

1. Open PowerShell or Command Prompt in the project folder:
   ```powershell
   cd C:\Users\91995\Desktop\kuku\project\NyayaSaathi
   ```

2. Check current status:
   ```powershell
   git status
   ```

3. Stage and commit all files:
   ```powershell
   git add .
   git commit -m "feat: complete Nyaya Saathi legal companion with cloud deployment configuration"
   ```

4. Set branch to `main`:
   ```powershell
   git branch -M main
   ```

5. Create a new public repository on GitHub named **`nyaya_saath`** (or your chosen name) at [github.com/new](https://github.com/new). Do not initialize it with a README, license, or .gitignore since you already have them locally.

6. Link your local project to GitHub and push (replace `notavii` with your GitHub username):
   ```powershell
   git remote add origin https://github.com/notavii/nyaya_saath.git
   git push -u origin main
   ```

### Option B: Using GitHub Desktop

1. Open **GitHub Desktop**.
2. Click **File** → **Add Local Repository...**.
3. Browse and select `C:\Users\91995\Desktop\kuku\project\NyayaSaathi`.
4. Enter a commit summary (e.g., `"Prepare Nyaya Saathi for Streamlit Community Cloud deployment"`).
5. Click **Commit to main** (or master).
6. Click **Publish repository** to GitHub.
   - Name: `nyaya_saath`
   - Uncheck "Keep this code private" if you want public sharing, or keep it private (Streamlit Cloud works with private repos too if authorized).
7. Click **Publish Repository**.

---

## 3. Deploy to Streamlit Community Cloud

Once your code is on GitHub:

1. Go to **[share.streamlit.io](https://share.streamlit.io)** and log in with your GitHub account.
2. Click the **"Create app"** (or **"New app"**) button.
3. Choose **"I already have an app"**.
4. Configure the deployment settings:
   - **Repository**: `notavii/nyaya_saath` (select from dropdown or type)
   - **Branch**: `main` (or `master`)
   - **Main file path**: `app.py`
   - **App URL**: Choose a custom subdomain (e.g. `nyaya-saathi.streamlit.app` or `nyayasaath.streamlit.app`)
5. **DO NOT click Deploy yet** — proceed to Step 4 below to configure secrets first!

---

## 4. Configure Application Secrets in Streamlit Cloud

Nyaya Saathi requires access to the Gemini API to power conversational reasoning and legal companion intelligence.

1. In the app creation modal, click **"Advanced settings..."** (or if already deployed, navigate to **Settings** → **Secrets** from your app's bottom-right context menu).
2. In the **Secrets** editor, enter your configuration in TOML format:

```toml
# Streamlit Secrets for Nyaya Saathi
GEMINI_API_KEY = "AIzaSy..."  # Replace with your actual Gemini API Key from Google AI Studio
GEMINI_MODEL = "gemini-3.1-flash-lite"
```

3. Click **Save**.
4. Click **Deploy!**.

---

## 5. What Happens During Cloud Deployment

Streamlit Community Cloud will automatically:
1. Provision a Linux container with Python 3.12.
2. Install packages from `requirements.txt`.
3. Load `.streamlit/config.toml` (enabling headless execution, disabling telemetry, configuring theme).
4. Launch `app.py`.
5. Connect to the prebuilt ChromaDB persistent vector database (`data/legal_sources/chroma_db/`) instantly.
6. The shared embedding model (`multilingual-e5-small`) will be cached via `@st.cache_resource`, ensuring that multiple concurrent users share the same resident memory without exhausting the 1GB RAM limit.

Your application will be live at:
`https://<your-subdomain>.streamlit.app`

---

## 6. Verification and Smoke Testing

Once deployed, perform these quick checks in your browser:

1. **Header & Badge Verification**:
   - Check that the title "Nyaya Saathi (न्याय साथी)" displays with the active status badge (`🟢 Online & Verified`).
2. **Session Turn Counter**:
   - Verify the sidebar shows "Session Turns: 0 / 40" and "Session State: Inactive / Ready".
3. **Knowledge Base Verification**:
   - Expand "Statutory Knowledge Base" in the sidebar. Verify:
     - 141 CPA 2019 provisions
     - 36 E-Commerce Rules (2020)
     - 4 General Rules (2020)
     - 1 E-Commerce Amendment (2021)
     - 1 e-Jagriti CC Filing Manual
4. **Interactive Chat Test**:
   - Type a test grievance:
     `"Flipkart delivered a damaged mobile phone and refused my replacement request."`
   - Confirm that:
     - The issue is classified as an e-commerce defective product dispute.
     - Extracted facts are displayed in structured cards with confidence badges.
     - Follow-up questions are offered.
     - Statutory citations under CPA 2019 and E-Commerce Rules 2020 are cited with official links.

---

## 7. Operational Notes & Limitations

| Dimension | Details & Safeguards |
| :--- | :--- |
| **Hosting Cost** | **$0.00** (Free hosting on Streamlit Community Cloud). |
| **RAM Limit** | ~1 GB slug limit. Safeguarded by `@st.cache_resource` for the embedding model (~470MB) + 14MB prebuilt ChromaDB. |
| **Session Isolation** | Every browser connection has an isolated `st.session_state`. No user data or grievance facts leak across sessions. |
| **Abuse Protection** | Inputs are capped at 2,500 characters, and sessions are capped at 40 conversational turns to avoid runaway token costs. |
| **Gemini Quota** | Uses Gemini Free Tier (15 RPM, 1,000,000 TPM, 1,500 requests/day). Sufficient for demo, prototype evaluation, and portfolio reviews. |
| **App Hibernation** | Free Streamlit Cloud apps sleep after several days of inactivity. Anyone visiting the URL can wake it up in ~30 seconds by clicking "Yes, get this app back up!". |
| **Continuous Deployment** | Whenever you run `git push origin main`, Streamlit Cloud automatically rebuilds and redeploys the latest code within 60 seconds. |

---

## 8. Troubleshooting

- **Error: "API Key Not Found" or fallback warning in sidebar:**
  - Verify that `GEMINI_API_KEY` is saved in the **Settings → Secrets** section in the Streamlit Cloud dashboard.
  - Restart the app via the Streamlit Cloud management menu.

- **Error: "OverCapacity / Resource Limit Exceeded":**
  - Check the app logs in the bottom-right menu (`Manage app` → `Logs`).
  - If the container restarts due to memory limits, the lazy-loading singleton pattern in `src/embeddings.py` prevents redundant model allocations.

- **Need to update the code?**
  - Simply commit and push your changes:
    ```powershell
    git add .
    git commit -m "fix: update companion response prompt"
    git push origin main
    ```
  - Streamlit Cloud will detect the push and automatically update your live app!
