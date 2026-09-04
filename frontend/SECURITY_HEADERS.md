# Production Security Headers

The VEIL / SAT-SA frontend is a static Single Page Application (SPA). To ensure production security, the web server or reverse proxy serving these static files (e.g., Nginx, Apache, AWS CloudFront) must be configured with the following security headers:

## Recommended Headers

```nginx
# 1. Strict-Transport-Security (HSTS)
# Enforces HTTPS connections.
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

# 2. X-Content-Type-Options
# Prevents MIME-type sniffing.
add_header X-Content-Type-Options "nosniff" always;

# 3. Referrer-Policy
# Controls how much referrer information is included with requests.
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

# 4. Permissions-Policy
# Disables access to powerful browser features (geolocation, camera, microphone).
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

# 5. Content-Security-Policy (CSP)
# Baseline CSP for this Vite React application.
# NOTE: connect-src below is a placeholder — the deploying operator must set
# this to wherever the backend API actually runs in their environment.
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self' <backend-api-origin>;" always;

# 6. X-Frame-Options (Clickjacking Protection)
# Prevents the site from being embedded in an iframe on other domains.
add_header X-Frame-Options "SAMEORIGIN" always;
```

## Environment Configuration

For deployment, set the following in your `.env.production` or CI/CD pipeline.
These have no default suitable for production — the deploying operator must
fill them in for their own environment:

- `VITE_API_BASE_URL`: The URL of the backend API for this deployment
  (defaults to `http://localhost:8000/api` for local/offline use).
