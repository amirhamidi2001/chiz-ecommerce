// Task 15.1.1.1: App composes HelmetProvider + DefaultSeo, so the sitewide default
// title/description reach the real document <head> on any route.
import { StrictMode } from 'react';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { act, render, waitFor } from '@testing-library/react';
import App from '../App';
import { DEFAULT_DESCRIPTION, DEFAULT_TITLE } from '../constants/seo';
import { headCanonicals, headHreflangs } from './seoTestHelpers';

// Stub the layout chrome and a page; this test only checks App's provider composition.
vi.mock('../components/Header', () => ({ default: () => null }));
vi.mock('../components/Footer', () => ({ default: () => null }));
vi.mock('../components/ChatWidget', () => ({ default: () => null }));
vi.mock('../pages/Home', () => ({ default: () => <div>home</div> }));
vi.mock('../pages/Faq', () => ({ default: () => <div>faq</div> }));
vi.mock('../pages/Contact', () => ({ default: () => <div>contact</div> }));
vi.mock('../pages/ResetPassword', () => ({ default: () => <div>reset</div> }));

describe('App root', () => {
  it('renders the default Persian title and description into document.head', async () => {
    window.history.pushState({}, '', '/');
    // StrictMode, as in main.jsx (double-invoked effects must not duplicate head tags).
    render(
      <StrictMode>
        <App />
      </StrictMode>,
    );
    await waitFor(() => expect(document.title).toBe(DEFAULT_TITLE));
    await waitFor(() =>
      expect(
        document.head.querySelector('meta[name="description"]')?.getAttribute('content'),
      ).toBe(DEFAULT_DESCRIPTION),
    );
    expect(document.head.querySelectorAll('title')).toHaveLength(1);
  });
});

// ─── Canonical links on every page (Task 15.1.4) ────────────────────────────────
// A real BrowserRouter on jsdom's real location, so this covers what a visitor/crawler gets.

describe('App canonical link', () => {
  const origin = () => window.location.origin;
  const visit = (url) => window.history.pushState({}, '', url);
  const renderApp = () =>
    render(
      <StrictMode>
        <App />
      </StrictMode>,
    );

  afterEach(() => {
    vi.unstubAllEnvs();
    visit('/');
  });

  it('points every page at its own clean URL: no query string, hash or trailing slash', async () => {
    visit('/faq/?utm_source=newsletter&sort=price#section');
    renderApp();
    await waitFor(() => expect(headCanonicals()).toEqual([`${origin()}/faq`]));
  });

  it('is the origin root for the home page', async () => {
    visit('/?ref=abc');
    renderApp();
    await waitFor(() => expect(headCanonicals()).toEqual([`${origin()}/`]));
  });

  it('follows client-side navigation instead of going stale after the first render', async () => {
    visit('/');
    renderApp();
    await waitFor(() => expect(headCanonicals()).toEqual([`${origin()}/`]));

    act(() => {
      visit('/contact?x=1');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    await waitFor(() => expect(headCanonicals()).toEqual([`${origin()}/contact`]));
  });

  it('has exactly one canonical link, not one per layer', async () => {
    visit('/faq');
    renderApp();
    await waitFor(() => expect(headCanonicals()).toHaveLength(1));
  });

  it('emits none on a password-reset URL, whose path carries a one-time token', async () => {
    visit('/reset-password/uid123/secret-token');
    renderApp();
    await waitFor(() => expect(document.title).toBe(DEFAULT_TITLE));
    expect(headCanonicals()).toEqual([]);
    expect(document.head.innerHTML).not.toContain('secret-token');
  });

  it('uses the configured VITE_SITE_URL instead of whichever host served the page', async () => {
    vi.stubEnv('VITE_SITE_URL', 'https://chiz.example');
    visit('/faq?x=1');
    renderApp();
    await waitFor(() => expect(headCanonicals()).toEqual(['https://chiz.example/faq']));
  });
});

// ─── Self-referencing hreflang on every page (Task 15.1.5) ──────────────────────
// Persian is the only built-out language, so a page names only ITSELF as fa-ir and x-default.

describe('App self-referencing hreflang', () => {
  const origin = () => window.location.origin;
  const visit = (url) => window.history.pushState({}, '', url);
  const renderApp = () =>
    render(
      <StrictMode>
        <App />
      </StrictMode>,
    );
  const selfPair = (href) => [
    { hreflang: 'fa-ir', href },
    { hreflang: 'x-default', href },
  ];

  afterEach(() => {
    vi.unstubAllEnvs();
    visit('/');
  });

  it('renders fa-ir and x-default, both pointing at the current page’s clean URL', async () => {
    visit('/faq/?utm_source=newsletter&sort=price#section');
    renderApp();
    await waitFor(() => expect(headHreflangs()).toEqual(selfPair(`${origin()}/faq`)));
  });

  it('does it for the home page too', async () => {
    visit('/?ref=abc');
    renderApp();
    await waitFor(() => expect(headHreflangs()).toEqual(selfPair(`${origin()}/`)));
  });

  it('is exactly the page’s canonical URL, never a different one', async () => {
    visit('/contact?x=1');
    renderApp();
    await waitFor(() => expect(headCanonicals()).toHaveLength(1));
    expect(headHreflangs().map((h) => h.href)).toEqual([headCanonicals()[0], headCanonicals()[0]]);
  });

  it('follows client-side navigation to the new page', async () => {
    visit('/');
    renderApp();
    await waitFor(() => expect(headHreflangs()).toEqual(selfPair(`${origin()}/`)));

    act(() => {
      visit('/contact?x=1');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    await waitFor(() => expect(headHreflangs()).toEqual(selfPair(`${origin()}/contact`)));
  });

  it('declares ONLY fa-ir and x-default: no English (or other) variant that does not exist', async () => {
    visit('/faq');
    renderApp();
    await waitFor(() => expect(headHreflangs()).toHaveLength(2));
    expect(headHreflangs().map((h) => h.hreflang).sort()).toEqual(['fa-ir', 'x-default']);
    expect(document.head.innerHTML).not.toMatch(/hreflang="en/i);
  });

  it('uses the configured VITE_SITE_URL origin', async () => {
    vi.stubEnv('VITE_SITE_URL', 'https://chiz.example');
    visit('/faq?x=1');
    renderApp();
    await waitFor(() => expect(headHreflangs()).toEqual(selfPair('https://chiz.example/faq')));
  });

  it('emits none where the page has no canonical (a password-reset URL with a token)', async () => {
    visit('/reset-password/uid123/secret-token');
    renderApp();
    await waitFor(() => expect(document.title).toBe(DEFAULT_TITLE));
    expect(headHreflangs()).toEqual([]);
  });
});

