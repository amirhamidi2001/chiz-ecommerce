// Self-referencing hreflang <link>s (Task 15.1.5), shared by <DefaultSeo> and <Seo> so every
// page gets the same pair (the default block steps aside while a page's <Seo> is mounted).
//
//   <link rel="alternate" hreflang="fa-ir"     href="<this page's canonical URL>">
//   <link rel="alternate" hreflang="x-default" href="<this page's canonical URL>">
//
// "This page IS the Persian/Iran version, and the fallback for everyone else": accurate and
// harmless. It is groundwork, not a feature: with no other language variants it has no effect
// on search results today.
//
// DEFERRED ON PURPOSE: real hreflang support (parallel fa/en URL structures with distinct,
// translated pages, each listing all the others) is NOT built and must not be faked. There is no
// English storefront (Django's LANGUAGES keeps "en" for admin/staff and future i18n only), and
// an hreflang="en" pointing at a missing or Persian-identical page would mislead search engines,
// which is worse than having none. Revisit when an English storefront is actually built; the
// reasoning and the checklist for that day are in backend/docs/adr/0003-hreflang-deferred.md.
//
// The href is the page's CANONICAL URL, never origin + pathname: hreflang must reference
// canonical URLs, and for /category?category=<slug> the path alone would name every category
// "/category". A page with no canonical (noindex search views, token URLs) gets no hreflang.
import { HREFLANG_DEFAULT, HREFLANG_SELF } from '../constants/seo';

export const hreflangLinks = (canonicalHref) =>
  canonicalHref
    ? [HREFLANG_SELF, HREFLANG_DEFAULT].map((code) => (
        <link key={code} rel="alternate" hrefLang={code} href={canonicalHref} />
      ))
    : [];
