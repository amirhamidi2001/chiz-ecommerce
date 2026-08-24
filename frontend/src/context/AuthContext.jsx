import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { authAPI, clearTokens, setTokens } from "../services/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // ── Re-hydrate user from an existing token on every mount ──────────────
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setLoading(false);
      return;
    }
    authAPI
      .getUser()
      .then(({ data }) => setUser(data))
      .catch(() => {
        // Token invalid / expired and refresh already failed inside the
        // interceptor — wipe storage so the user sees the login page cleanly.
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      })
      .finally(() => setLoading(false));
  }, []);

  // ── login ───────────────────────────────────────────────────────────────
  // Calls POST /auth/login/, stores tokens, then fetches the user object so
  // AuthContext.user is populated before the caller navigates anywhere.
  const login = useCallback(async (credentials) => {
    const { data } = await authAPI.login(credentials);
    setTokens({ access: data.access, refresh: data.refresh });
    const { data: profile } = await authAPI.getUser();
    setUser(profile);
    return profile;
  }, []);

  // ── loginWithOtp ───────────────────────────────────────────────────────
  // Completes the phone/OTP flow (Feature 2.3.2): the phone-entry and
  // code-entry components (Tasks 2.3.2.1/2.3.2.2) call authAPI.requestOtp()
  // / authAPI.verifyOtp() themselves — this method is only the final
  // hand-off once verification has already succeeded server-side. Mirrors
  // login()'s exact shape (fetch tokens → store → hydrate user → return
  // profile) for consistency, and additionally surfaces `isNewUser` from
  // the verify response so the caller can redirect a brand-new user to a
  // "complete your profile" step (empty first_name/last_name on
  // OTP-created accounts — see Task 2.3.1.3).
  const loginWithOtp = useCallback(async (phoneNumber, code) => {
    const { data } = await authAPI.verifyOtp(phoneNumber, code);
    setTokens({ access: data.access, refresh: data.refresh });
    const { data: profile } = await authAPI.getUser();
    setUser(profile);
    return { profile, isNewUser: data.is_new_user };
  }, []);

  // ── hydrateUser ─────────────────────────────────────────────────────────
  // Call this after *any* flow that sets tokens externally (e.g. register)
  // without going through login().  It fetches GET /auth/user/ and writes the
  // result into context, making isAuthenticated flip to true immediately.
  const hydrateUser = useCallback(async () => {
    try {
      const { data } = await authAPI.getUser();
      setUser(data);
      return data;
    } catch {
      return null;
    }
  }, []);

  // ── logout ──────────────────────────────────────────────────────────────
  const logout = useCallback(async () => {
    try {
      const refresh = localStorage.getItem("refresh_token");
      if (refresh) await authAPI.logout(refresh);
    } catch {
      /* ignore — blacklist failure must not block the UI */
    } finally {
      clearTokens();
      setUser(null);
    }
  }, []);

  // ── updateUser ──────────────────────────────────────────────────────────
  // Merge a partial update into the cached user (e.g. after profile PATCH).
  const updateUser = useCallback((partial) => {
    setUser((prev) => (prev ? { ...prev, ...partial } : prev));
  }, []);

  // ── context value ────────────────────────────────────────────────────────
  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: !!user,
      isAdmin: user?.type === 2 || user?.type === 3,
      login,
      loginWithOtp,
      logout,
      hydrateUser,
      updateUser,
    }),
    [user, loading, login, loginWithOtp, logout, hydrateUser, updateUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
};

export default AuthContext;
