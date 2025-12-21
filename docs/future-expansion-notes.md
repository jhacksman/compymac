# Future Expansion Notes

This document captures potential features that were considered but deferred, with steelman arguments for their future implementation.

## Deploy Tool Expansions

### ngrok Expose Command

**Status:** Deferred (stub exists in deploy tool)

**What it does:** Temporarily exposes a local port to the internet via ngrok tunneling, returning a public URL that routes to localhost.

**Steelman case for implementation:**

1. **Rapid iteration during development** - When building features that require external service integration (OAuth callbacks, payment webhooks, CI/CD triggers), developers currently must deploy to test. ngrok allows testing these integrations against local code with instant feedback loops, reducing deploy-test-fix cycles from minutes to seconds.

2. **Collaborative debugging** - When a bug only reproduces in a specific environment or with specific data, expose allows a teammate or user to interact with your exact local state. This is invaluable for debugging issues that are difficult to reproduce or describe.

3. **Demo without deploy risk** - Product demos often happen before code is production-ready. Expose allows showing working functionality to stakeholders without the risk of deploying incomplete features or the overhead of maintaining a staging environment.

4. **Webhook development is painful without it** - Services like Stripe, GitHub, Slack, and Twilio require publicly accessible URLs for webhooks. Without ngrok, developers must either deploy every change or use service-specific CLI tools (which don't exist for all services). ngrok provides a universal solution.

5. **Mobile app testing** - When developing backends for mobile apps, expose allows testing against real devices on different networks without deploying, which is especially useful for testing edge cases around network conditions.

**Implementation notes:**
- Requires NGROK_AUTHTOKEN environment variable
- Free tier has limitations (random URLs, connection limits)
- Consider cloudflared as an alternative (free, no account required for basic use)

### Netlify Frontend Deployment

**Status:** Deferred (GitHub Pages implemented instead)

**What it does:** Deploys static frontend builds to Netlify's CDN with automatic HTTPS, preview deployments, and optional serverless functions.

**Steelman case for implementation:**

1. **Preview deployments per PR** - Netlify automatically creates unique preview URLs for every pull request. This allows reviewers to test changes in isolation without affecting production or other PRs. GitHub Pages only supports a single deployment per repo.

2. **Serverless functions at the edge** - Netlify Functions allow deploying serverless API endpoints alongside the frontend. For simple backends (form handlers, API proxies, auth flows), this eliminates the need for a separate backend deployment entirely.

3. **Instant rollbacks** - Every Netlify deploy is immutable and instantly rollback-able. If a deploy breaks production, one click restores the previous version. GitHub Pages requires pushing a revert commit and waiting for rebuild.

4. **Split testing and gradual rollouts** - Netlify supports A/B testing and percentage-based traffic splitting between deploys. This enables safe feature rollouts and data-driven UX decisions without additional infrastructure.

5. **Form handling built-in** - Netlify Forms captures form submissions without any backend code. For landing pages, contact forms, or feedback collection, this removes significant complexity.

6. **Build plugins ecosystem** - Netlify's plugin system allows customizing the build process (image optimization, lighthouse audits, cache invalidation) without maintaining custom CI/CD pipelines.

7. **Better for SPAs** - Netlify handles SPA routing (redirecting all paths to index.html) automatically. GitHub Pages requires workarounds (404.html hack) that can cause issues with SEO and deep linking.

**Implementation notes:**
- Requires NETLIFY_AUTH_TOKEN environment variable
- API-based deployment via Netlify's deploy API
- Consider supporting both Netlify and GitHub Pages, letting users choose based on their needs

## When to Revisit

Consider implementing these features when:
- Users report friction with the current deployment workflow
- A specific use case emerges that GitHub Pages + Fly.io cannot address
- The project expands to support more complex deployment scenarios
