// Open Graph <meta> tags (Task 15.1.3), shared by <DefaultSeo> and <Seo> so the two can never
// drift apart. A plain function returning an array of <meta> elements (not a component):
// <Helmet> only understands head elements as direct children.
//
// Every page needs the COMPLETE set because <DefaultSeo> steps aside while a page's <Seo> is
// mounted (see context/seoContext.js); og:site_name / og:locale therefore come from here for
// both. Empty values are dropped, so a missing price or image never becomes content="undefined".
import { STORE_NAME } from '../constants/store';
import { OG_LOCALE } from '../constants/seo';

const present = (value) => value !== undefined && value !== null && String(value).trim() !== '';

export const openGraphMeta = ({
  type = 'website',
  title,
  description,
  url,
  image,
  imageAlt,
  imageWidth,
  imageHeight,
  price,
} = {}) =>
  [
    ['og:site_name', STORE_NAME],
    ['og:locale', OG_LOCALE],
    ['og:type', type],
    ['og:title', title],
    ['og:description', description],
    ['og:url', url],
    ['og:image', image],
    // Alt text and size only describe an image that is actually present.
    ['og:image:alt', image ? imageAlt : undefined],
    ['og:image:width', image ? imageWidth : undefined],
    ['og:image:height', image ? imageHeight : undefined],
    ['product:price:amount', price?.amount],
    ['product:price:currency', price?.amount !== undefined ? price?.currencyCode : undefined],
  ]
    .filter(([, content]) => present(content))
    .map(([property, content]) => <meta key={property} property={property} content={String(content)} />);
