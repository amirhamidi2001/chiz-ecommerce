// DOM readers for page-level SEO tests (Task 15.1.1.2): what is really in document.head.
export const headTitles = () => Array.from(document.head.querySelectorAll('title'));
export const headDescriptions = () =>
  Array.from(document.head.querySelectorAll('meta[name="description"]'));

// Open Graph readers (Task 15.1.3): every <meta property="..."> in the real document <head>.
export const headMeta = (property) =>
  Array.from(document.head.querySelectorAll(`meta[property="${property}"]`)).map((m) =>
    m.getAttribute('content'),
  );
export const headOgProperties = () =>
  Array.from(document.head.querySelectorAll('meta[property]')).map((m) =>
    m.getAttribute('property'),
  );

/**
 * Pin window.location.origin for a test and return a function that puts the previous value back.
 * (Some older tests replace window.location wholesale and never restore it, so don't rely on it.)
 */
export const stubLocationOrigin = (origin, pathname) => {
  const saved = window.location;
  Object.defineProperty(window, 'location', {
    configurable: true,
    writable: true,
    value: { origin, href: `${origin}/`, ...(pathname === undefined ? {} : { pathname }) },
  });
  return () =>
    Object.defineProperty(window, 'location', { configurable: true, writable: true, value: saved });
};

// Canonical + robots readers (Task 15.1.4): the <link rel="canonical"> hrefs and <meta name="robots">
// contents in the real document <head>.
export const headCanonicals = () =>
  Array.from(document.head.querySelectorAll('link[rel="canonical"]')).map((l) =>
    l.getAttribute('href'),
  );
export const headRobots = () =>
  Array.from(document.head.querySelectorAll('meta[name="robots"]')).map((m) =>
    m.getAttribute('content'),
  );

// hreflang reader (Task 15.1.5): [{ hreflang, href }] for every <link rel="alternate" hreflang>
// ANYWHERE in the document (not just <head>), so a stray tag React left in the body is seen too.
export const headHreflangs = () =>
  Array.from(document.querySelectorAll('link[rel="alternate"][hreflang]')).map((l) => ({
    hreflang: l.getAttribute('hreflang'),
    href: l.getAttribute('href'),
  }));

