// Page-specific <title>/<meta description> (Task 15.1.1.2). Render one per page, only once the
// data it describes has loaded.
//
//   <Seo title={buildProductTitle(product)} description={buildProductMetaDescription(product)} />
//
// Optional `jsonLd` (a plain object, e.g. from buildProductStructuredData) adds a
// <script type="application/ld+json">. On React 19 that script is rendered in place rather than
// hoisted into <head> (React only hoists async external scripts); search engines read JSON-LD
// from anywhere in the document, so that is fine. It unmounts with the page.
//
// Optional `og` (e.g. from buildProductOpenGraph) sets the page's Open Graph tags. Every <Seo>
// emits the full set (site name, locale, type, title, description, image) with sensible defaults
// (type "website", the page title/description, the branded default image), so a page only passes
// what differs. Link-preview crawlers (WhatsApp, Telegram) read these: see the note in
// openGraphMeta.jsx and the Task 15.1.3 report on what they can and cannot see in an SPA.
//
// `canonical` is the page's canonical URL (build it with utils/canonical.js): a string to emit it,
// null for "this page deliberately has none" (noindex pages), or omitted to canonicalize to the
// current clean path. `robots` is a robots meta value such as "noindex, follow".
//
// With nothing usable to say (no title, canonical or robots: data still loading, or missing) it
// renders NOTHING and registers no override, so the sitewide default from <DefaultSeo> stays in
// place. That avoids ever emitting "undefined | Chiz" while a fetch is in flight. A page that
// knows its canonical/robots before its title does (a listing whose category name is still
// loading) passes just those: the title and description then fall back to the sitewide ones. A missing description falls back to the
// sitewide one so the page never ends up with a title but no description.
import { useEffect } from 'react';
import { Helmet } from 'react-helmet-async';
import { useSeo } from '../context/seoContext';
import { DEFAULT_DESCRIPTION, DEFAULT_TITLE } from '../constants/seo';
import { buildPageCanonical } from '../utils/canonical';
import { defaultOgImage, serializeJsonLd } from '../utils/seo';
import { hreflangLinks } from './hreflangLinks';
import { openGraphMeta } from './openGraphMeta';

const usable = (value) =>
  typeof value === 'string' && value.trim() !== '' && !/\bundefined\b|\bnull\b/.test(value);

const Seo = ({ title, description, jsonLd, og, canonical, robots }) => {
  const { registerPageSeo } = useSeo();
  const hasCanonical = typeof canonical === 'string' && canonical !== '';
  const active = usable(title) || hasCanonical || Boolean(robots);

  useEffect(() => (active ? registerPageSeo() : undefined), [active, registerPageSeo]);

  if (!active) return null;
  const pageTitle = usable(title) ? title : DEFAULT_TITLE;
  const metaDescription = usable(description) ? description : DEFAULT_DESCRIPTION;
  // Omitted -> this page's own clean path. (Read at render: every page that uses <Seo> re-renders
  // on navigation anyway, and the listings pass an explicit canonical built from their state.)
  const canonicalHref =
    canonical === undefined
      ? buildPageCanonical(typeof window !== 'undefined' ? window.location?.pathname : '')
      : canonical;
  return (
    <Helmet>
      <title>{pageTitle}</title>
      <meta name="description" content={metaDescription} />
      {canonicalHref && <link rel="canonical" href={canonicalHref} />}
      {hreflangLinks(canonicalHref)}
      {robots && <meta name="robots" content={robots} />}
      {openGraphMeta({
        title: pageTitle,
        description: metaDescription,
        // The branded default only when the page supplies no image of its own, so its
        // width/height/alt never get attached to someone else's picture.
        ...(og?.image ? {} : defaultOgImage()),
        ...og,
      })}
      {jsonLd && <script type="application/ld+json">{serializeJsonLd(jsonLd)}</script>}
    </Helmet>
  );
};

export default Seo;
