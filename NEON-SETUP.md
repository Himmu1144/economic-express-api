# Neon setup verification

Project: `curly-king-72601696` / `production`, AWS Singapore, PostgreSQL 18, Free plan. Public image bucket: `article-images`.

## What changed

- Installed Neon CLI 8.17.1 and its agent tooling through the user-supplied `neon init` command. Browser authentication completed.
- Added `neon.ts`, private Node configuration package and lockfile to the Django backend root. Config reuses the existing public `article-images` bucket; it does not create an unrelated private assets bucket.
- `config/settings.py` loads ignored Neon environment files without overriding process variables, accepts `AWS_ENDPOINT_URL_S3`/`AWS_REGION`, and uses S3 path-style addressing with SigV4. Existing Django ORM/psycopg retained; server-side cursors disabled for transaction pooling and connection health checks enabled.
- `news/checks.py` accepts a public HTTPS storage endpoint without requiring a custom domain. Added pinned python-dotenv dependency and updated developer setup documentation.
- Backend `.env.local` holds credentials; frontend `.env.local` contains only API/site URLs, the webhook secret and public image hostname. Secrets and the local demo login file are gitignored.
- Applied Django migrations via the direct Neon URL, imported 29 sample articles / 9 categories / videos, and created a clearly labeled demo verification article and editor account.

## Evidence

`neon deploy`:
```
No changes — branch production already matches the policy.
Utilized services: Postgres, Object Storage
Pulled 7 Neon variables into .env.local
```

Migrations were first applied on a temporary Neon branch. The full regression suite on that branch reported:
```
Ran 18 tests in 180.104s
OK
```
The temporary branch was deleted after verification. See `evidence/neon-tests.log` and `evidence/neon-migrations.log`.

Storage/API workflow (see `evidence/neon-e2e.json`):
- Created a draft through the Django admin form; public API returned 404.
- Uploaded a cover through that form; Neon public URL returned 200; decoded image is WebP, width 1600.
- Uploaded an inline image through the authenticated CMS upload endpoint; public URL returned 200.
- Published through the admin form; public API returned the matching Neon cover URL and article content.
- Independent object-store upload/read/delete probe passed, including exact byte comparison.
- Author photo upload succeeded and was linked to the demo article.
- Final Chrome verification passed: article HTTP 200, optimized cover and inline images loaded, editor login succeeded, TinyMCE initialized, zero JavaScript errors. See `evidence/neon-browser.json`.

Frontend production build:
```
✓ Compiled successfully
Finished TypeScript
✓ Generating static pages using 9 workers (57/57) in 49s
```
The generated routes include `/article/neon-upload-workflow-check`. Full output: `evidence/neon-frontend-build.log`.

## Failures and limits

- Initial setup was interrupted by an automatic approval-review usage limit; resumed after the user's continue message.
- An extra final author-avatar/webhook-count probe stalled and was interrupted; the author upload itself had succeeded, and the primary storage/API/browser checks passed.
- First production build timed out on API requests. Current API diagnostics found no locks or long-running queries; the retry completed successfully. Hosted connection/cold-start performance still needs measurement.
- First browser CMS check found missing static assets because the API had started before collectstatic. A subsequent hot reload triggered macOS Objective-C fork errors. A full restart after collection fixed the local setup; the final browser check passed.
- Webhook attempts failed while the local frontend was not running; the persistent outbox retained them and a worker pass delivered them after startup.
- This provisions Neon database/storage, **not public Django or frontend hosting**. API and site currently run locally at ports 8001 and 3001. Local HTTP redirect/origin exceptions must be replaced with the deployed HTTPS settings.
- No public repository was created; the source remains local. No credentials are included in this report.
- A demo editor credential file is at `.demo-login.json` in this backend folder (ignored by Git). Do not commit or share that file publicly.

The earlier production-readiness report remains a launch checklist. Its missing-cloud-storage blocker is superseded by this Neon verification; production web hosting, backups and other launch items remain separate work.
