// Context + hook for page-level SEO overrides (Task 15.1.1.2). The provider component lives in
// SeoProvider.jsx (kept separate so each file exports only components or only non-components).
//
// Why this exists: on React 19, react-helmet-async 3.x renders <title>/<meta> for React to
// hoist into <head> and does NOT dedupe, so a page-level <Helmet> would sit NEXT TO the
// sitewide default instead of replacing it (two meta descriptions in the DOM). Instead, pages
// render <Seo>, which registers here, and <DefaultSeo> renders only while nothing is registered.
import { createContext, useContext } from 'react';

// Outside a provider (e.g. a page rendered alone in a test) registering is a harmless no-op.
export const SeoContext = createContext({ hasPageSeo: false, registerPageSeo: () => () => {} });

export const useSeo = () => useContext(SeoContext);
