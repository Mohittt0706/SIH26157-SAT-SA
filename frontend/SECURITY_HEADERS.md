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
# Note: You may need to adjust `connect-src` if your API is hosted on a different domain.
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self' https://your-api-domain.com;" always;

# 6. X-Frame-Options (Clickjacking Protection)
# Prevents the site from being embedded in an iframe on other domains.
add_header X-Frame-Options "SAMEORIGIN" always;
```

## Environment Configuration

For production deployment, ensure the following environment variables are set in your `.env.production` or CI/CD pipeline:

- `VITE_API_BASE_URL`: The absolute URL of your production backend API (e.g., `https://api.example.com/api`).
- `VITE_SITE_URL`: The absolute URL where this frontend is deployed (e.g., `https://veil.example.com`). This is used for Open Graph, Canonical URLs, and the Sitemap.
