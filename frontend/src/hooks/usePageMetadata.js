import { useEffect } from "react";

export default function usePageMetadata({ title, description, path }) {
  useEffect(() => {
    // 1. Update Title
    if (title) {
      document.title = title;
    }

    // 2. Update Meta Description
    if (description) {
      let metaDescription = document.querySelector('meta[name="description"]');
      if (metaDescription) {
        metaDescription.setAttribute("content", description);
      } else {
        metaDescription = document.createElement("meta");
        metaDescription.name = "description";
        metaDescription.content = description;
        document.head.appendChild(metaDescription);
      }
    }

    // 3. Update Canonical URL & OG URL
    if (path !== undefined) {
      // Use import.meta.env.VITE_SITE_URL if available, else fallback to window.location.origin
      const baseUrl = import.meta.env.VITE_SITE_URL || window.location.origin;
      const canonicalUrl = `${baseUrl}${path}`;

      let linkCanonical = document.querySelector('link[rel="canonical"]');
      if (linkCanonical) {
        linkCanonical.setAttribute("href", canonicalUrl);
      } else {
        linkCanonical = document.createElement("link");
        linkCanonical.rel = "canonical";
        linkCanonical.href = canonicalUrl;
        document.head.appendChild(linkCanonical);
      }

      let metaOgUrl = document.querySelector('meta[property="og:url"]');
      if (metaOgUrl) {
        metaOgUrl.setAttribute("content", canonicalUrl);
      } else {
        metaOgUrl = document.createElement("meta");
        metaOgUrl.setAttribute("property", "og:url");
        metaOgUrl.content = canonicalUrl;
        document.head.appendChild(metaOgUrl);
      }
    }
  }, [title, description, path]);
}
