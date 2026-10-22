# 📱 SIM Lookup

A Streamlit app where a user enters **their own** ID card number and sees the SIMs
registered against it. Gemini Flash writes a short, friendly summary.

## Important: data source and privacy

There is no public API for "SIMs by ID number". You must use data you are
authorised to use (e.g. your own telecom's customer records, or an official API
you have access to). Do **not** scrape government/operator sites or use leaked
databases. Anyone with an ID number could otherwise look up another person's
details.

Built-in safeguards:
- ID numbers are hashed in memory, never stored or logged
- SIM numbers are masked in the UI and before being sent to Gemini
- Gemini never receives the ID number
- Consent checkbox and a simple per-session rate limit

For production, add real verification (OTP to the registered phone or login)
before showing results. The rate limit here is per browser session only.

## Run locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
export GEMINI_API_KEY="your-key"   # Windows: set GEMINI_API_KEY=your-key
streamlit run app.py
```

Without a data file the app runs in demo mode with fake data (try `1234567890123`).

## Using your own data

Create a CSV with these columns and set `SIM_DATA_PATH` to its path:

`id_number, sim_number, operator, status, registered_on`

Never commit this CSV to GitHub.

## Settings

| Name | Purpose |
|------|---------|
| `GEMINI_API_KEY` | Gemini key from https://aistudio.google.com/apikey (optional) |
| `GEMINI_MODEL` | Defaults to `gemini-2.5-flash` |
| `ID_HASH_SALT` | Any long random string |
| `SIM_DATA_PATH` | Path to your CSV (omit for demo mode) |

## Push to GitHub

```bash
git init
printf "venv/\n__pycache__/\n.streamlit/secrets.toml\n*.csv\n.env\n" > .gitignore
git add .
git commit -m "Initial commit"
git branch -M main
# create an empty repo on github.com first, then:
git remote add origin https://github.com/YOUR_USERNAME/sim-lookup.git
git push -u origin main
```

## Deploy on Streamlit Community Cloud

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click **Create app** → choose your repo, branch `main`, file `app.py`.
3. Open **Advanced settings → Secrets** and paste:
   ```toml
   GEMINI_API_KEY = "your-key"
   ID_HASH_SALT = "a-long-random-string"
   ```
4. Click **Deploy**.

Real data: do not put it in a public repo. Load it from a private source
(database or private storage) and keep credentials in Secrets.
