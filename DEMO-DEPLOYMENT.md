# Hosted client demo

Verified 3 November 2026.

- Website: https://economic-express-demo.vercel.app
- Editor CMS: https://economic-express-api.onrender.com/admin/
- Liveness: https://economic-express-api.onrender.com/health/
- Source: https://github.com/Himmu1144/economic-express-api (public, per owner’s updated instruction).

The frontend is in Nishnat’s Vercel workspace, `nishnat121003-5696s-projects`, project `economic-express-demo`. The API is a Render Free Docker service in Singapore, `srv-dbkvfm0u01pc73ee53n0`. Neon continues to hold the PostgreSQL database and public `article-images` bucket. No Google Cloud VM or Cloud Run service was provisioned.

## Keep-warm job

Google Cloud project `bcrm121`, region `asia-southeast1`, job `economic-express-demo-health`: HTTP GET `/health/` every ten minutes (`*/10 * * * *`, Asia/Kolkata). The job is enabled. A real Cloud Scheduler execution log recorded HTTP 200; the next scheduled execution also completed successfully. Liveness makes zero database queries and does not refresh Yahoo prices.

This reduces normal 15-minute idle sleeps. Render Free can still restart or hit account quotas, so it is not an uptime guarantee. Cloud Scheduler includes three free jobs per billing account; otherwise its published charge is $0.10/job/month. Remove the job after the demo period.

## Checks completed

- Render Linux/amd64 Docker build passed; `/health/` and TinyMCE static assets returned HTTP 200 even with an unreachable test database.
- Public API home, article and editor login respond over HTTPS. CORS allows the exact Vercel production domain. Secure cookies, HTTPS redirect and trusted proxy protocol are enabled.
- Real hosted editor login, cover upload, draft privacy and publication passed. Uploaded cover was resized to 1600-pixel WebP and loaded publicly from Neon.
- Editing a hosted article refreshed the public frontend through the revalidation webhook.
- Both temporary technical verification stories were returned to draft. They return 404 through the API and public site; all 29 sample news stories remain public.
- Public home, article, category, search, sitemap and robots returned 200. Unknown article/category returned actual HTTP 404.
- Browser confirmed home/article content renders and the cleaned homepage contains no technical-test links.
- Vercel production build is Ready; build output completed in 46 seconds. The first build overlapped a backend configuration restart and failed with 502s. A later attempt hit the eight-second read timeout under prerender load. Bounded GET retries and lower static-generation concurrency were added, type-checked and tested (transient 502, network failure, persistent 503 and 404 cases), then deployment succeeded.
- The local Vercel CLI log stream sometimes disconnected despite a successful remote deployment; remote deployment status and logs were used for verification.

Evidence is in `evidence/hosted-*.json`, `evidence/hosted-vercel-build.log`, and `evidence/hosted-scheduler.json`. No credentials are included.

## Access and later changes

The demo editor username is `demo-editor`. Its password remains only in the ignored local `.demo-login.json` file in the backend folder; do not put that file in Git or share it publicly. Backend credentials are stored as Render environment variables. Frontend credentials and URLs are set in Vercel’s production environment. GitHub visibility was changed only after the owner explicitly requested it.

Render deployment currently uses the already-initialized Neon schema. Apply future migrations through the Neon direct URL before deploying schema-dependent releases. The ten-minute liveness job does not run the scheduled-publication/retry worker; immediate publish/edit cache invalidation works, but reliable scheduled publishing still requires that worker to be hosted.

The editorial screenshot guide is still deferred. The earlier `PRODUCTION-CHECK.md` remains a separate full-launch checklist; this document records the working client demo.
