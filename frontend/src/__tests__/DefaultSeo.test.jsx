// Task 15.1.1.1: react-helmet-async is wired in and the sitewide default metadata reaches
// the REAL document <head> (not just the React tree).
import { afterEach, beforeEach, describe, it, expect } from 'vitest';
import { StrictMode } from 'react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { HelmetProvider } from 'react-helmet-async';
import DefaultSeo from '../components/DefaultSeo';
import Seo from '../components/Seo';
import SeoProvider from '../context/SeoProvider';
import { WithSeo } from './seoTestUtils';
import {
  headTitles,
  headDescriptions,
  headMeta,
  headOgProperties,
  headCanonicals,
  headHreflangs,
  headRobots,
  stubLocationOrigin,
} from './seoTestHelpers';
import { DEFAULT_DESCRIPTION, DEFAULT_TITLE } from '../constants/seo';

const metaDescription = () =>
  document.head.querySelector('meta[name="description"]')?.getAttribute('content');

describe('DefaultSeo', () => {
  it('sets the Persian default title and description in document.head', async () => {
    render(
      <HelmetProvider>
        <DefaultSeo />
      </HelmetProvider>,
    );
    // Helmet applies head changes asynchronously, so wait for the DOM.
    await waitFor(() => expect(document.title).toBe(DEFAULT_TITLE));
    await waitFor(() => expect(metaDescription()).toBe(DEFAULT_DESCRIPTION));
    expect(document.head.querySelector('title')).toHaveTextContent(DEFAULT_TITLE);
    expect(metaDescription()).toBe(DEFAULT_DESCRIPTION);
    expect(document.title).toMatch(/[\u0600-\u06FF]/); // contains Persian script
  });
});

// Task 15.1.1.2: pages override the default through <Seo>; the default must step aside while a
// page is mounted and come back when it unmounts (i.e. when the visitor navigates away).
describe('Seo overriding DefaultSeo', () => {
  it('replaces the default (one title, one description) and restores it on unmount, under StrictMode', async () => {
    const { rerender } = render(
      <StrictMode>
        <WithSeo>
          <Seo title="سرم ویتامین سی | Chiz" description="توضیح محصول" />
        </WithSeo>
      </StrictMode>,
    );
    await waitFor(() => expect(document.title).toBe('سرم ویتامین سی | Chiz'));
    await waitFor(() => expect(headDescriptions()).toHaveLength(1));
    expect(headDescriptions()[0].getAttribute('content')).toBe('توضیح محصول');
    expect(headTitles()).toHaveLength(1);

    rerender(
      <StrictMode>
        <WithSeo>{null}</WithSeo>
      </StrictMode>,
    );
    await waitFor(() => expect(document.title).toBe(DEFAULT_TITLE));
    await waitFor(() => expect(headDescriptions()[0]?.getAttribute('content')).toBe(DEFAULT_DESCRIPTION));
    expect(headTitles()).toHaveLength(1);
    expect(headDescriptions()).toHaveLength(1);
  });

  it('falls back to the sitewide description when a page supplies a title only', async () => {
    render(
      <WithSeo>
        <Seo title="صفحه تست | Chiz" />
      </WithSeo>,
    );
    await waitFor(() => expect(document.title).toBe('صفحه تست | Chiz'));
    await waitFor(() => expect(headDescriptions()[0]?.getAttribute('content')).toBe(DEFAULT_DESCRIPTION));
    expect(headDescriptions()).toHaveLength(1);
  });

  it('renders nothing (default stays) for an empty or broken title', async () => {
    render(
      <WithSeo>
        <Seo title="undefined | Chiz" />
        <Seo title="" />
        <Seo title={undefined} />
      </WithSeo>,
    );
    await waitFor(() => expect(document.title).toBe(DEFAULT_TITLE));
    expect(headTitles()).toHaveLength(1);
  });
});

// Task 15.1.3: sitewide Open Graph defaults, and their hand-off to a page's own tags.
describe('Open Graph defaults', () => {
  const ORIGIN = 'https://shop.example';
  let restoreLocation;
  beforeEach(() => {
    restoreLocation = stubLocationOrigin(ORIGIN);
  });
  afterEach(() => restoreLocation());

  it('DefaultSeo sets og:site_name, og:type and og:locale plus a branded absolute-URL card', async () => {
    render(
      <HelmetProvider>
        <DefaultSeo />
      </HelmetProvider>,
    );
    await waitFor(() => expect(headMeta('og:site_name')).toEqual(['Chiz']));
    expect(headMeta('og:type')).toEqual(['website']);
    expect(headMeta('og:locale')).toEqual(['fa_IR']);
    expect(headMeta('og:title')).toEqual([DEFAULT_TITLE]);
    expect(headMeta('og:description')).toEqual([DEFAULT_DESCRIPTION]);
    expect(headMeta('og:image')).toEqual([`${ORIGIN}/og-default.jpg`]);
    expect(headMeta('og:image:width')).toEqual(['1200']);
    expect(headMeta('og:image:height')).toEqual(['630']);
    expect(headMeta('product:price:amount')).toEqual([]);
  });

  it('a page <Seo og> replaces the defaults (one of each), keeps site name/locale, and hands back on unmount', async () => {
    const page = (
      <StrictMode>
        <WithSeo>
          <Seo
            title="سرم | Chiz"
            description="توضیح"
            og={{ type: 'product', title: 'سرم', image: 'https://cdn.example/a.jpg', price: { amount: '100', currencyCode: 'IRR' } }}
          />
        </WithSeo>
      </StrictMode>
    );
    const { rerender } = render(page);

    await waitFor(() => expect(headMeta('og:type')).toEqual(['product']));
    expect(headMeta('og:title')).toEqual(['سرم']);
    expect(headMeta('og:image')).toEqual(['https://cdn.example/a.jpg']);
    expect(headMeta('og:image:width')).toEqual([]); // the default image's size is not borrowed
    expect(headMeta('og:site_name')).toEqual(['Chiz']);
    expect(headMeta('og:locale')).toEqual(['fa_IR']);
    expect(headMeta('product:price:amount')).toEqual(['100']);
    const props = headOgProperties();
    expect(props.filter((p, i) => props.indexOf(p) !== i)).toEqual([]);

    rerender(
      <StrictMode>
        <WithSeo>{null}</WithSeo>
      </StrictMode>,
    );
    await waitFor(() => expect(headMeta('og:type')).toEqual(['website']));
    expect(headMeta('og:title')).toEqual([DEFAULT_TITLE]);
    expect(headMeta('og:image')).toEqual([`${ORIGIN}/og-default.jpg`]);
    expect(headMeta('product:price:amount')).toEqual([]);
  });

  it('defaults a page <Seo> to type website, its own title/description and the branded image', async () => {
    render(
      <WithSeo>
        <Seo title="صفحه تست | Chiz" description="توضیح تست" />
      </WithSeo>,
    );
    await waitFor(() => expect(headMeta('og:title')).toEqual(['صفحه تست | Chiz']));
    expect(headMeta('og:type')).toEqual(['website']);
    expect(headMeta('og:description')).toEqual(['توضیح تست']);
    expect(headMeta('og:image')).toEqual([`${ORIGIN}/og-default.jpg`]);
  });

  it('omits og:image entirely, rather than emitting a relative one, when there is no origin', async () => {
    restoreLocation();
    restoreLocation = stubLocationOrigin('');
    render(
      <HelmetProvider>
        <DefaultSeo />
      </HelmetProvider>,
    );
    await waitFor(() => expect(headMeta('og:site_name')).toEqual(['Chiz']));
    expect(headMeta('og:image')).toEqual([]);
  });
});

// Task 15.1.4: canonical / robots contract of <Seo> and its hand-off from <DefaultSeo>.
describe('Seo canonical and robots', () => {
  const ORIGIN = 'https://shop.example';
  let restoreLocation;
  beforeEach(() => {
    restoreLocation = stubLocationOrigin(ORIGIN, '/about/');
  });
  afterEach(() => restoreLocation());

  it('DefaultSeo canonicalizes to the clean current path (here outside any router)', async () => {
    render(
      <HelmetProvider>
        <DefaultSeo />
      </HelmetProvider>,
    );
    await waitFor(() => expect(headCanonicals()).toEqual([`${ORIGIN}/about`]));
  });

  it('a page canonical replaces the default one (exactly one link) and the default returns on unmount', async () => {
    const { rerender } = render(
      <StrictMode>
        <WithSeo>
          <Seo title="سرم | Chiz" canonical="https://shop.example/product/serum" />
        </WithSeo>
      </StrictMode>,
    );
    await waitFor(() => expect(headCanonicals()).toEqual(['https://shop.example/product/serum']));

    rerender(
      <StrictMode>
        <WithSeo>{null}</WithSeo>
      </StrictMode>,
    );
    await waitFor(() => expect(headCanonicals()).toEqual([`${ORIGIN}/about`]));
  });

  it('defaults to the page’s own clean path when no canonical is passed', async () => {
    render(
      <WithSeo>
        <Seo title="صفحه | Chiz" />
      </WithSeo>,
    );
    await waitFor(() => expect(document.title).toBe('صفحه | Chiz'));
    expect(headCanonicals()).toEqual([`${ORIGIN}/about`]);
  });

  it('canonical={null} means "no canonical", and the default one does not sneak back in', async () => {
    render(
      <WithSeo>
        <Seo title="جستجو | Chiz" canonical={null} robots="noindex, follow" />
      </WithSeo>,
    );
    await waitFor(() => expect(headRobots()).toEqual(['noindex, follow']));
    expect(headCanonicals()).toEqual([]);
    expect(document.title).toBe('جستجو | Chiz');
  });

  it('canonical alone (no title yet) still applies it, with the sitewide title in place', async () => {
    render(
      <WithSeo>
        <Seo canonical="https://shop.example/category?category=skincare" />
      </WithSeo>,
    );
    await waitFor(() =>
      expect(headCanonicals()).toEqual(['https://shop.example/category?category=skincare']),
    );
    expect(document.title).toBe(DEFAULT_TITLE);
    expect(headTitles()).toHaveLength(1);
    expect(headDescriptions()).toHaveLength(1);
    expect(headMeta('og:title')).toEqual([DEFAULT_TITLE]);
  });

  it('robots alone is enough to activate it, and is removed again on unmount', async () => {
    const { rerender } = render(
      <WithSeo>
        <Seo robots="noindex, follow" />
      </WithSeo>,
    );
    await waitFor(() => expect(headRobots()).toEqual(['noindex, follow']));
    expect(document.title).toBe(DEFAULT_TITLE);

    rerender(<WithSeo>{null}</WithSeo>);
    await waitFor(() => expect(headRobots()).toEqual([]));
  });

  it('adds no robots meta unless asked', async () => {
    render(
      <WithSeo>
        <Seo title="صفحه | Chiz" />
      </WithSeo>,
    );
    await waitFor(() => expect(document.title).toBe('صفحه | Chiz'));
    expect(headRobots()).toEqual([]);
  });
});

// DefaultSeo must follow the ROUTER, not read window.location once. A MemoryRouter never touches
// window.location, and DefaultSeo is a stable element here that only a router subscription can
// update, so this fails for any implementation that reads the address bar instead.
describe('DefaultSeo canonical follows router navigation', () => {
  const Nav = ({ to }) => {
    const navigate = useNavigate();
    return <button onClick={() => navigate(to)}>go</button>;
  };

  it('updates when the route changes, and strips the query string and trailing slash', async () => {
    const restore = stubLocationOrigin('https://shop.example', '/never-used');
    render(
      <HelmetProvider>
        <SeoProvider>
          <MemoryRouter initialEntries={['/faq?utm_source=x']}>
            <DefaultSeo />
            <Nav to="/contact/?x=1#top" />
          </MemoryRouter>
        </SeoProvider>
      </HelmetProvider>,
    );
    await waitFor(() => expect(headCanonicals()).toEqual(['https://shop.example/faq']));

    fireEvent.click(screen.getByText('go'));
    await waitFor(() => expect(headCanonicals()).toEqual(['https://shop.example/contact']));
    restore();
  });
});

// Task 15.1.5: the hreflang pair comes from whichever block is active, never both.
describe('hreflang hand-off between DefaultSeo and Seo', () => {
  const ORIGIN = 'https://shop.example';
  let restoreLocation;
  beforeEach(() => {
    restoreLocation = stubLocationOrigin(ORIGIN, '/about');
  });
  afterEach(() => restoreLocation());
  const pair = (href) => [
    { hreflang: 'fa-ir', href },
    { hreflang: 'x-default', href },
  ];

  it('DefaultSeo declares the page itself; a page <Seo> replaces it (one pair), and it returns on unmount', async () => {
    const { rerender } = render(
      <StrictMode>
        <WithSeo>
          <Seo title="سرم | Chiz" canonical="https://shop.example/product/serum" />
        </WithSeo>
      </StrictMode>,
    );
    await waitFor(() => expect(headHreflangs()).toEqual(pair('https://shop.example/product/serum')));

    rerender(
      <StrictMode>
        <WithSeo>{null}</WithSeo>
      </StrictMode>,
    );
    await waitFor(() => expect(headHreflangs()).toEqual(pair(`${ORIGIN}/about`)));
  });

  it('a page with canonical={null} has none, and the default pair does not sneak back in', async () => {
    render(
      <WithSeo>
        <Seo title="جستجو | Chiz" canonical={null} robots="noindex, follow" />
      </WithSeo>,
    );
    await waitFor(() => expect(headRobots()).toEqual(['noindex, follow']));
    expect(headHreflangs()).toEqual([]);
  });
});

