// Sitewide SEO defaults (Task 15.1.1.1). Any page without its own <Helmet>
// falls back to these; page-specific titles/descriptions arrive in Task 15.1.1.2.
//
// Kept in one place so index.html's pre-hydration fallback, the baseline <Helmet>
// in DefaultSeo, and the smoke test cannot drift apart.
import { STORE_NAME } from './store';

// Open Graph (Task 15.1.3). Persian (Iran) locale, in og:locale's language_TERRITORY format.
export const OG_LOCALE = 'fa_IR';

// Branded fallback share image, a static file in public/ (served at the site root). It is the
// store banner (public/logo.webp) cropped to the standard 1200x630 link-card size and saved as
// JPEG, the format every link-preview crawler reads (WebP support in WhatsApp is unreliable).
// og:image must be ABSOLUTE, so it is prefixed with the site origin where it is used.
export const DEFAULT_OG_IMAGE_PATH = '/og-default.jpg';
export const DEFAULT_OG_IMAGE_WIDTH = 1200;
export const DEFAULT_OG_IMAGE_HEIGHT = 630;
export const DEFAULT_TITLE = `${STORE_NAME} | فروشگاه آنلاین لوازم آرایشی و بهداشتی`;

export const DEFAULT_DESCRIPTION =
  `${STORE_NAME}؛ مرجع خرید آنلاین لوازم آرایشی، محصولات مراقبت از پوست و مو و ` +
  'لوازم بهداشتی. محصولات را بر اساس برند، نوع پوست و نوع مو پیدا کنید و ' +
  'با اطمینان سفارش دهید.';

// hreflang (Task 15.1.5). Persian is the only built-out storefront language, so a page declares
// only ITSELF: as the Persian (Iran) version and as the x-default. No "en" alternate exists, and
// inventing one would point search engines at a page that isn't there. Full multi-language support
// is deliberately deferred: backend/docs/adr/0003-hreflang-deferred.md
export const HREFLANG_SELF = 'fa-ir';
export const HREFLANG_DEFAULT = 'x-default';
