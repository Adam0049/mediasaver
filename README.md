# MediaSaver v3 starter

This project contains a static frontend for Cloudflare Workers static assets and a separate FastAPI/yt-dlp backend intended for a container host such as Render. The frontend alone cannot download social-media content.

## Important limits
- This starter is for publicly accessible content that you own or are authorized to download. It does not accept platform passwords or cookies and does not bypass private-account controls, DRM, or login restrictions.
- The backend is experimental. Site extractors change, some platforms may block downloads, and free hosting can sleep, time out, or enforce resource limits.
- Render free-tier availability and limits may change. Review the provider's current pricing/limits before deploying.
- The backend limits input domains, file size (500 MB by default), duration (60 minutes by default), and request rate. Do not deploy a public unauthenticated downloader.

## Deploy frontend
1. Deploy `index.html` to the existing Cloudflare static-assets project as you did previously.
2. The frontend needs the backend URL and API key to be configured in **Download service settings** after the backend is deployed.

## Deploy backend using Render Blueprint
1. Create a GitHub repository and upload the contents of this project, preserving the `backend/` folder and `render.yaml` at the repository root.
2. In Render, choose **New + → Blueprint** and connect that repository.
3. Review the service settings and deploy. Render should generate `MEDIA_SAVER_API_KEY` automatically.
4. Copy the deployed service URL (for example, `https://mediasaver-api.onrender.com`).
5. In the Render service's **Environment** settings, set `FRONTEND_ORIGINS` to the exact Cloudflare URL origin, e.g. `https://mediasaver-abdoda1994.workers.dev` (no trailing slash). Save/redeploy.
6. Copy the generated `MEDIA_SAVER_API_KEY` value from Render's Environment settings. Keep it private.
7. Open the Cloudflare website → **Download service settings**. Enter the Render service URL and the API key, then click **Save settings** and **Test connection**.
8. Test only with a public link to media you are authorized to download.

## Local backend test
From `backend/`:
```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
export MEDIA_SAVER_API_KEY='replace-with-a-long-random-secret'
export FRONTEND_ORIGINS='http://localhost:8080'
uvicorn app:app --reload --port 8000
```
On Windows PowerShell, use `$env:MEDIA_SAVER_API_KEY='...'` and `$env:FRONTEND_ORIGINS='http://localhost:8080'` instead of `export`.

## Troubleshooting
- `401`: API key mismatch.
- CORS/network error: `FRONTEND_ORIGINS` must exactly match the Cloudflare origin.
- `503`: set `MEDIA_SAVER_API_KEY` in backend environment.
- `422`: media may be unsupported, unavailable, restricted, or over configured limits.
- Free hosting may spin down and the first request may take a while.
