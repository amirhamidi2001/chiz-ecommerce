// Counts the pages currently supplying their own <title>/<meta description>. See seoContext.js.
import { useCallback, useMemo, useState } from 'react';
import { SeoContext } from './seoContext';

export const SeoProvider = ({ children }) => {
  const [count, setCount] = useState(0);

  // Returns the cleanup function, so it can be passed straight back from a useEffect.
  const registerPageSeo = useCallback(() => {
    setCount((c) => c + 1);
    return () => setCount((c) => c - 1);
  }, []);

  const value = useMemo(
    () => ({ hasPageSeo: count > 0, registerPageSeo }),
    [count, registerPageSeo],
  );
  return <SeoContext.Provider value={value}>{children}</SeoContext.Provider>;
};

export default SeoProvider;
