Verdict: NOT READY

Update: Neon database and public image storage are now connected and verified; see `NEON-SETUP.md` for current evidence. The original checklist below records the pre-Neon assessment.

Checked 3 November 2026. The backend and frontend integration are implemented and pass local production-mode functional checks. This is **not approval to launch**: cloud storage, hosted security/backups, and the stated mobile performance target are not verified/passing. No deployment or public repository was created.

Blockers (must fix before launch):
- Configure and verify the real R2/S3 bucket, upload credentials, public HTTPS image domain and frontend `IMAGE_STORAGE_HOST`. Cover, inline and author upload processing is implemented; actual cloud upload/delivery and survival across redeploy cannot be verified without credentials. Tests use in-memory storage, not a production substitute.
- Supply final domains, strong production secrets, allowed hosts, CORS/CSRF origins and HTTPS ingress. Run `manage.py check --deploy` with the actual environment. The local check correctly rejects missing storage settings/CSRF origins, HTTP frontend URL and the local HTTPS-redirect exception. Secure cookies and HTTPS/HSTS are the production defaults. Configure and verify real client IP forwarding so rate limits do not group every visitor under a proxy IP.
- Deploy a persistent worker for scheduled publication and durable webhook retries. `python manage.py run_workers` is required beside the web process; a sleeping free web service alone cannot guarantee publication within seconds.
- Enable automated hosted PostgreSQL backups with an agreed retention period, and repeat the restore drill against that provider. A local PostgreSQL dump/restore passed; no hosted backup policy has been configured or verified.
- Mobile Lighthouse performance misses the handoff's 92–99 baseline on home/category: final home **82**, article **93**, category **88**. Accessibility, best practices and SEO are **100** on all three. Investigate the attached reports on the intended hosting before launch. No frontend redesign was performed.
- Replace or editorially approve the demo news and static ticker fallback before presenting the site as a live publication. The seed is explicitly opt-in (`seed --demo`). Static ticker values are not live quotes; the existing UI's Delayed label does not communicate the backend's new `source`/`stale` diagnostics.
- Confirm a suitable hosting plan. An all-free production stack is not established, especially for a client/commercial site and an always-running worker.

Should fix soon:
- Investigate a Next.js MaxListenersExceededWarning observed during repeated production route checks; the smoke checks passed, but a longer soak test is warranted.
- Resolve the 16 moderate frontend development-tool audit findings using compatible dependency updates. No high/critical findings were reported. Do not apply npm's suggested major downgrades blindly.
- Add monitoring for webhook backlog, worker health, API errors, storage failures and stale ticker age. The outbox retries failures and logs them, but no external alerting account is configured.
- Add a branded unavailable state for cold/uncached pages during API outages. Previously cached home/article/category pages remained available during the tested outage. A cold cache cannot be guaranteed available without a durable content cache; the API layer deliberately refuses to silently replace live news with samples.
- Review homepage image delivery, unused JavaScript, render-blocking requests and LCP discovery from Lighthouse. Lab conditions differ from the supplied earlier mock benchmark, so these results establish a failed target, not proof that backend latency caused the difference.
- Add retention policies for delivered webhook events, old daily view counters and authentication logs. Expired rate-limit buckets are pruned by the worker.
- Draft preview is an authenticated, no-store CMS preview rather than an exact public-template preview. Author photos are returned by the API; the existing article template still displays initials. Treat further presentation changes as frontend recommendations.

Nice to have:
- External uptime/error monitoring, staff MFA, and editorial audit-history UI beyond created/updated user and timestamps.
- A dedicated scheduled-job platform if publication timing must survive web-host downtime.
- Automated Lighthouse baselines on the deployed frontend and a larger-data load test against hosted PostgreSQL.

Checks run:

| Handoff check | Result | Evidence / limit |
|---|---|---|
| Production frontend build | PASS | `next build` completed with TypeScript checking; served with `next start`, Next 16.4.4, configured API. |
| PostgreSQL backend | PASS | PostgreSQL 17 in an isolated local Docker container; migrations, seed and 18 regression tests passed. API served by Gunicorn with `DEBUG=False`. SQLite was used only for an initial test pass. |
| 1. Route integration | PASS locally | Home, article, category, tag, search, calculator, four static pages, sitemap, robots and OG image returned 200. Unknown article/category and archived article returned real HTTP 404 after fixing streaming behavior. See `evidence/integration-results.json`. |
| Seed / mock contract comparison | PASS data; visual comparison partial | Imported all 29 cards, 9 categories, four videos and all six supplied full bodies. Preserved titles/images/tags/key points. Derived reading times, recent demo timestamps and required fallback captions intentionally differ. Browser checks showed no runtime errors; an independent route-by-route mock screenshot comparison was not completed. |
| 2. Editor flow | PARTIAL | Real admin form draft → publish → edit → archive verified, including homepage/category/search/sitemap updates and Breaking payload. Real browser login and TinyMCE initialization passed with zero JavaScript errors (`evidence/admin-browser-results.json`). Upload validation and inline upload endpoint pass tests with memory storage; live cloud upload remains unverified. |
| Roles / recovery | PASS | Writers restricted to own active drafts, forced draft on save; editors publish/archive; restore returns draft; soft deletion retains the row. Writer changelist/add form and authenticated preview restrictions tested. |
| 3. Scheduled post | PASS locally | Real two-minute deadline: API 404 before, API/frontend 200 after; visible about 0.8 seconds after deadline. Persistent worker running. `evidence/schedule-results.json`. |
| 4. Backend outage | PASS for warm cache | Stopped API: home, known article and category still returned 200 with cached content. No mock fallback for a configured API. Cold-cache availability not guaranteed. `evidence/outage-results.json`. |
| Ticker Yahoo failure | PASS in regression test | Forced Yahoo timeout preserves saved last-good data. Empty storage returns seven-key static fallback. Refresh is asynchronous with ten-minute retry spacing; actual Yahoo availability is not guaranteed. |
| 5. Security | PARTIAL | HTML script/event-handler/javascript-URL removal, decoded-image size/type checks, writer ownership, view/newsletter throttling and five-failure login lockout tested. HTTPS defaults present; production host/origin/storage secrets absent. Pattern scan found no private-key/AWS-key material in authored source; no real environment file tracked. |
| Dependency audits | PASS required severity threshold | pip-audit: no known vulnerabilities after updating the isolated environment's pip. npm audit: 0 high, 0 critical, 16 moderate. Raw reports included. |
| 6. API performance | PASS locally | 100 sequential HTTP requests: home p95 **46.5 ms**, **12 SQL queries**, with all nine category sections. Sliced prefetch avoids a query per category; card authors/categories use select_related. This does not establish hosted or concurrent-load latency. |
| 6. Mobile Lighthouse | FAIL baseline | Home 82 / article 93 / category 88 performance; all three A11y 100, Best Practices 100, SEO 100. Final CLS approximately 0.00023 / 0 / 0.00005. Reports in `evidence/`. |
| 7. SEO | PASS locally; production domain pending | Rendered article title, description, canonical, absolute OG image and parseable NewsArticle JSON-LD verified. Publisher logo corrected to existing `/icon.svg`. Sitemap includes every public article across pagination, excludes drafts/future/archive; robots points to configured site's sitemap. Production URL still needs configuration. |
| 8. Data safety | PARTIAL | `pg_dump -Fc` → new database → `pg_restore --exit-on-error` succeeded; restored 31 article rows (including temporary test rows) and 9 categories at time of drill. Automated hosted backups not verified. |
| 9. Hosting | NOT CONFIGURED | Only local production-mode processes were used. No infrastructure account, public repo, or deployment was created. |
| Final code checks | PASS | 18 PostgreSQL tests; `makemigrations --check --dry-run`: no changes; Ruff undefined/unused-name checks pass; frontend `git diff --check` passes. |

What I changed in the frontend (file + reason):
- `src/lib/api.ts`: bounded API requests; mock mode only when no API URL exists; propagate configured-API failures rather than fabricate news; follow all sitemap pages; support nullable lead/live home videos; treat out-of-range article-list pages as empty.
- `src/lib/types.ts`: optional cover alt text from the backend.
- `next.config.ts`: allow the configured `IMAGE_STORAGE_HOST` over HTTPS.
- `src/app/page.tsx`: wire approved video component to `home.videos`; guard empty video/lead lists. No layout redesign.
- `src/app/article/[slug]/page.tsx`: correct production-only dynamic-route validation, missing metadata handling, cover alt text and nonexistent publisher-logo URL.
- `src/app/category/[slug]/page.tsx`: use notFound for missing category metadata.
- `src/app/layout.tsx`: allow runtime pathname access in the shared header without a null fallback/layout jump; existing header design preserved.
- `src/proxy.ts`: check published visibility before streaming, returning real 404s for unknown/archived articles and unknown categories. Adds one small API query on these routes. On API outage, allows Next to use existing cached content rather than infer deletion.

Videos choice: `home.videos[]` is wired to the frontend; `/api/videos/` is also available. The player-compatible `id` is the YouTube ID. Videos are ordered, activatable and editable by administrators.

Mock fallback decision: **not acceptable for a configured production API**. A finance news site must not silently publish sample stories as current reporting. Mock mode is retained only when `NEXT_PUBLIC_API_URL` is empty. Cached real responses provide the tested outage behavior. Configure the API environment variable for all live deployments.

Hosting setup used + env vars needed:
- Actual verification: local Next production build/server, Gunicorn, PostgreSQL 17, separate worker, Chrome/Lighthouse. No live cloud credentials were used. Local test secrets were generated outside either repository; the test database contains only sample/test data.
- Frontend: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SITE_URL`, `REVALIDATE_SECRET`, `IMAGE_STORAGE_HOST`.
- Backend: `DATABASE_URL` (PostgreSQL; require TLS on hosted connections), `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`, `REVALIDATE_SECRET`, `BREAKING_HOURS=12`; `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL` for R2, `AWS_S3_REGION_NAME`, `AWS_S3_CUSTOM_DOMAIN`; optional seed-only `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD`. `TRUST_PROXY_PROTO` only after verifying ingress behavior. Do not deploy with `TESTING=True` or the local `SECURE_SSL_REDIRECT=False` exception.
- Vercel Hobby is restricted to personal/non-commercial use; this client publication needs a suitable plan rather than an assumption that Hobby is allowed. [Vercel Hobby](https://vercel.com/docs/plans/hobby).
- Render Free web services sleep after 15 minutes idle and can take about a minute to wake. Cold requests and a two-second worker cannot be assumed covered by frontend caching. [Render free services](https://render.com/docs/free).
- Railway's trial is limited; its subsequent Free plan supplies $1 monthly credit, which does not establish that this web+worker workload fits. [Railway trial](https://docs.railway.com/pricing/free-trial).
- Neon's current Free plan lists 1 GB/project, 100 CU-hours/project, and limited restore history (up to six hours or 1 GB changes). Size/retention requirements must be checked against the actual account. A continuously polling worker can prevent database scale-to-zero, so budget for its usage. [Neon pricing](https://neon.com/pricing).
- R2 supports the implemented S3 storage backend; its free allowance and operation/storage billing still require a configured account and workload estimate. Internet egress is free, but operations/storage are not unlimited. [R2 pricing](https://developers.cloudflare.com/r2/pricing/).

The editorial operations guide has intentionally not been written.
