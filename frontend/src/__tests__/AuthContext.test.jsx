import { render, screen, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AuthProvider, useAuth } from "../context/AuthContext";

// ─── Module mocks ────────────────────────────────────────────────────────────
// Must be hoisted above any imports that use these modules.
vi.mock("../services/api", () => ({
  authAPI: {
    login: vi.fn(),
    getUser: vi.fn(),
    logout: vi.fn(),
  },
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
}));

// Pull the mocked references so tests can configure them.
import { authAPI, setTokens, clearTokens } from "../services/api";

// ─── localStorage mock ───────────────────────────────────────────────────────
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: vi.fn((key) => store[key] ?? null),
    setItem: vi.fn((key, value) => { store[key] = String(value); }),
    removeItem: vi.fn((key) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
    _store: () => store,   // test-only helper
  };
})();

Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
  writable: true,
});

// ─── Consumer component ──────────────────────────────────────────────────────
// Renders every value from the context so tests can assert via the DOM.
const AuthConsumer = () => {
  const { user, loading, isAuthenticated, isAdmin, login, logout, hydrateUser, updateUser } =
    useAuth();

  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="isAuthenticated">{String(isAuthenticated)}</span>
      <span data-testid="isAdmin">{String(isAdmin)}</span>
      <span data-testid="user">{user ? JSON.stringify(user) : "null"}</span>
      <button onClick={() => login({ email: "a@b.com", password: "pw" }).catch(() => { })}>
        login
      </button>
      <button onClick={() => logout()}>logout</button>
      <button onClick={() => hydrateUser()}>hydrate</button>
      <button onClick={() => updateUser({ first_name: "Updated" })}>
        updateUser
      </button>
    </div>
  );
};

// Convenience: render AuthProvider + consumer and wait for the mount effect to
// finish (i.e. loading flips to false) so each test starts from a stable state.
const renderAuth = async () => {
  let utils;
  await act(async () => {
    utils = render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    );
  });
  return utils;
};

// ─── Setup / teardown ────────────────────────────────────────────────────────
beforeEach(() => {
  vi.clearAllMocks();
  localStorageMock.clear();
  // Default: no token in storage
  localStorageMock.getItem.mockReturnValue(null);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ════════════════════════════════════════════════════════════════════════════
// 1. INITIAL STATE
// ════════════════════════════════════════════════════════════════════════════
describe("Initial state", () => {
  it("exposes loading=true, user=null, isAuthenticated=false before the effect resolves", async () => {
    // Keep getUser pending so we can inspect the transient state.
    let resolveGetUser;
    authAPI.getUser.mockReturnValue(
      new Promise((res) => { resolveGetUser = res; })
    );
    localStorageMock.getItem.mockReturnValue("some-token");

    let utils;
    act(() => {
      utils = render(
        <AuthProvider>
          <AuthConsumer />
        </AuthProvider>
      );
    });

    expect(screen.getByTestId("loading").textContent).toBe("true");
    expect(screen.getByTestId("isAuthenticated").textContent).toBe("false");
    expect(screen.getByTestId("user").textContent).toBe("null");

    // Settle the pending promise so React doesn't warn about state updates
    // after unmount.
    await act(async () => {
      resolveGetUser({ data: { id: 1 } });
    });
  });

  it("sets loading=false and keeps user=null when no token is stored", async () => {
    localStorageMock.getItem.mockReturnValue(null);
    await renderAuth();

    expect(screen.getByTestId("loading").textContent).toBe("false");
    expect(screen.getByTestId("user").textContent).toBe("null");
    expect(screen.getByTestId("isAuthenticated").textContent).toBe("false");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 2. REHYDRATION — useEffect on mount
// ════════════════════════════════════════════════════════════════════════════
describe("Rehydration (useEffect on mount)", () => {
  it("fetches user and sets state when a valid access_token exists", async () => {
    localStorageMock.getItem.mockReturnValue("valid-token");
    const profile = { id: 1, email: "user@example.com", type: 1 };
    authAPI.getUser.mockResolvedValueOnce({ data: profile });

    await renderAuth();

    expect(authAPI.getUser).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("user").textContent).toBe(JSON.stringify(profile));
    expect(screen.getByTestId("loading").textContent).toBe("false");
    expect(screen.getByTestId("isAuthenticated").textContent).toBe("true");
  });

  it("does NOT call authAPI.getUser when no token is present", async () => {
    localStorageMock.getItem.mockReturnValue(null);
    await renderAuth();

    expect(authAPI.getUser).not.toHaveBeenCalled();
  });

  it("removes access_token and refresh_token from localStorage on invalid/expired token", async () => {
    localStorageMock.getItem.mockReturnValue("expired-token");
    authAPI.getUser.mockRejectedValueOnce(new Error("401 Unauthorized"));

    await renderAuth();

    expect(localStorageMock.removeItem).toHaveBeenCalledWith("access_token");
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("refresh_token");
  });

  it("sets loading=false after a failed rehydration", async () => {
    localStorageMock.getItem.mockReturnValue("bad-token");
    authAPI.getUser.mockRejectedValueOnce(new Error("Unauthorized"));

    await renderAuth();

    expect(screen.getByTestId("loading").textContent).toBe("false");
    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("keeps user=null after a failed rehydration", async () => {
    localStorageMock.getItem.mockReturnValue("bad-token");
    authAPI.getUser.mockRejectedValueOnce(new Error("Unauthorized"));

    await renderAuth();

    expect(screen.getByTestId("isAuthenticated").textContent).toBe("false");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 3. login()
// ════════════════════════════════════════════════════════════════════════════
describe("login()", () => {
  const credentials = { email: "a@b.com", password: "pw" };
  const tokens = { access: "acc-token", refresh: "ref-token" };
  const profile = { id: 42, email: "user@example.com", type: 1 };

  beforeEach(() => {
    // No token on mount → skip rehydration
    localStorageMock.getItem.mockReturnValue(null);
    authAPI.login.mockResolvedValue({ data: tokens });
    authAPI.getUser.mockResolvedValue({ data: profile });
  });

  it("calls authAPI.login with the provided credentials", async () => {
    await renderAuth();

    await act(async () => {
      screen.getByRole("button", { name: "login" }).click();
    });

    expect(authAPI.login).toHaveBeenCalledWith(credentials);
  });

  it("calls setTokens with access and refresh from the login response", async () => {
    await renderAuth();

    await act(async () => {
      screen.getByRole("button", { name: "login" }).click();
    });

    expect(setTokens).toHaveBeenCalledWith({
      access: tokens.access,
      refresh: tokens.refresh,
    });
  });

  it("calls authAPI.getUser after storing tokens", async () => {
    await renderAuth();

    await act(async () => {
      screen.getByRole("button", { name: "login" }).click();
    });

    // setTokens must be called first, then getUser
    const setTokensOrder = setTokens.mock.invocationCallOrder[0];
    const getUserOrder = authAPI.getUser.mock.invocationCallOrder[0];
    expect(setTokensOrder).toBeLessThan(getUserOrder);
  });

  it("updates user state with the profile returned by getUser", async () => {
    await renderAuth();

    await act(async () => {
      screen.getByRole("button", { name: "login" }).click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("user").textContent).toBe(JSON.stringify(profile));
    });
    expect(screen.getByTestId("isAuthenticated").textContent).toBe("true");
  });

  it("returns the fetched profile from login()", async () => {
    await renderAuth();

    // Call login directly via the hook to capture the return value.
    let returned;
    const LoginCapture = () => {
      const { login } = useAuth();
      return (
        <button
          onClick={async () => {
            returned = await login(credentials);
          }}
        >
          capture-login
        </button>
      );
    };

    await act(async () => {
      render(
        <AuthProvider>
          <LoginCapture />
        </AuthProvider>
      );
    });

    await act(async () => {
      screen.getByRole("button", { name: "capture-login" }).click();
    });

    expect(returned).toEqual(profile);
  });

  it("propagates errors thrown by authAPI.login", async () => {
    authAPI.login.mockRejectedValueOnce(new Error("Invalid credentials"));
    await renderAuth();

    let caughtError;
    const ErrorCapture = () => {
      const { login } = useAuth();
      return (
        <button
          onClick={async () => {
            try {
              await login(credentials);
            } catch (e) {
              caughtError = e;
            }
          }}
        >
          err-login
        </button>
      );
    };

    await act(async () => {
      render(
        <AuthProvider>
          <ErrorCapture />
        </AuthProvider>
      );
    });

    await act(async () => {
      screen.getByRole("button", { name: "err-login" }).click();
    });

    expect(caughtError).toBeDefined();
    expect(caughtError.message).toBe("Invalid credentials");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 4. logout()
// ════════════════════════════════════════════════════════════════════════════
describe("logout()", () => {
  const profile = { id: 1, email: "user@example.com", type: 1 };

  beforeEach(() => {
    // Start authenticated
    localStorageMock.getItem.mockImplementation((key) => {
      if (key === "access_token") return "acc";
      if (key === "refresh_token") return "ref";
      return null;
    });
    authAPI.getUser.mockResolvedValue({ data: profile });
    authAPI.logout.mockResolvedValue({});
  });

  it("calls authAPI.logout with the stored refresh token", async () => {
    await renderAuth();

    await act(async () => {
      screen.getByRole("button", { name: "logout" }).click();
    });

    expect(authAPI.logout).toHaveBeenCalledWith("ref");
  });

  it("calls clearTokens after logging out", async () => {
    await renderAuth();

    await act(async () => {
      screen.getByRole("button", { name: "logout" }).click();
    });

    expect(clearTokens).toHaveBeenCalledTimes(1);
  });

  it("resets user to null after logout", async () => {
    await renderAuth();

    // Ensure user is set first
    await waitFor(() =>
      expect(screen.getByTestId("isAuthenticated").textContent).toBe("true")
    );

    await act(async () => {
      screen.getByRole("button", { name: "logout" }).click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("user").textContent).toBe("null");
      expect(screen.getByTestId("isAuthenticated").textContent).toBe("false");
    });
  });

  it("does NOT call authAPI.logout when no refresh_token is stored", async () => {
    localStorageMock.getItem.mockImplementation((key) => {
      if (key === "access_token") return "acc";
      return null; // no refresh token
    });

    await renderAuth();

    await act(async () => {
      screen.getByRole("button", { name: "logout" }).click();
    });

    expect(authAPI.logout).not.toHaveBeenCalled();
    expect(clearTokens).toHaveBeenCalledTimes(1);
  });

  it("still calls clearTokens and resets user even when authAPI.logout throws", async () => {
    authAPI.logout.mockRejectedValueOnce(new Error("Server error"));
    await renderAuth();

    await waitFor(() =>
      expect(screen.getByTestId("isAuthenticated").textContent).toBe("true")
    );

    await act(async () => {
      screen.getByRole("button", { name: "logout" }).click();
    });

    await waitFor(() => {
      expect(clearTokens).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("user").textContent).toBe("null");
    });
  });

  it("does not throw when authAPI.logout fails", async () => {
    authAPI.logout.mockRejectedValueOnce(new Error("Network error"));
    await renderAuth();

    await expect(
      act(async () => {
        screen.getByRole("button", { name: "logout" }).click();
      })
    ).resolves.not.toThrow();
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 5. hydrateUser()
// ════════════════════════════════════════════════════════════════════════════
describe("hydrateUser()", () => {
  beforeEach(() => {
    localStorageMock.getItem.mockReturnValue(null);
    // Suppress rehydration call
    authAPI.getUser.mockResolvedValue({ data: null });
  });

  it("fetches user via authAPI.getUser and updates state", async () => {
    const profile = { id: 7, email: "hydrated@example.com", type: 1 };
    authAPI.getUser.mockResolvedValueOnce({ data: profile });

    await renderAuth();

    await act(async () => {
      screen.getByRole("button", { name: "hydrate" }).click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("user").textContent).toBe(JSON.stringify(profile));
      expect(screen.getByTestId("isAuthenticated").textContent).toBe("true");
    });
  });

  it("returns the fetched user data", async () => {
    const profile = { id: 7, email: "hydrated@example.com", type: 1 };
    let returned;

    const HydrateCapture = () => {
      const { hydrateUser } = useAuth();
      return (
        <button
          onClick={async () => {
            returned = await hydrateUser();
          }}
        >
          capture-hydrate
        </button>
      );
    };

    authAPI.getUser.mockResolvedValueOnce({ data: profile });

    await act(async () => {
      render(
        <AuthProvider>
          <HydrateCapture />
        </AuthProvider>
      );
    });

    await act(async () => {
      screen.getByRole("button", { name: "capture-hydrate" }).click();
    });

    expect(returned).toEqual(profile);
  });

  it("returns null when authAPI.getUser fails", async () => {
    authAPI.getUser.mockRejectedValueOnce(new Error("Unauthorized"));
    let returned = "NOT_SET";

    const HydrateCapture = () => {
      const { hydrateUser } = useAuth();
      return (
        <button
          onClick={async () => {
            returned = await hydrateUser();
          }}
        >
          hydrate-fail
        </button>
      );
    };

    await act(async () => {
      render(
        <AuthProvider>
          <HydrateCapture />
        </AuthProvider>
      );
    });

    await act(async () => {
      screen.getByRole("button", { name: "hydrate-fail" }).click();
    });

    expect(returned).toBeNull();
  });

  it("does not crash the app when getUser throws during hydrateUser", async () => {
    authAPI.getUser.mockRejectedValueOnce(new Error("500 Internal Server Error"));
    await renderAuth();

    await expect(
      act(async () => {
        screen.getByRole("button", { name: "hydrate" }).click();
      })
    ).resolves.not.toThrow();
  });

  it("leaves user as null when hydrateUser fails", async () => {
    authAPI.getUser.mockRejectedValueOnce(new Error("Network error"));
    await renderAuth();

    await act(async () => {
      screen.getByRole("button", { name: "hydrate" }).click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("user").textContent).toBe("null");
    });
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 6. updateUser()
// ════════════════════════════════════════════════════════════════════════════
describe("updateUser()", () => {
  const profile = { id: 1, first_name: "Jane", last_name: "Doe", type: 1 };

  beforeEach(() => {
    localStorageMock.getItem.mockReturnValue("acc");
    authAPI.getUser.mockResolvedValue({ data: profile });
  });

  it("merges a partial update into the existing user", async () => {
    await renderAuth();

    await waitFor(() =>
      expect(screen.getByTestId("user").textContent).toBe(JSON.stringify(profile))
    );

    // The consumer's updateUser button hard-codes { first_name: "Updated" }
    await act(async () => {
      screen.getByRole("button", { name: "updateUser" }).click();
    });

    const expected = { ...profile, first_name: "Updated" };
    await waitFor(() => {
      expect(screen.getByTestId("user").textContent).toBe(JSON.stringify(expected));
    });
  });

  it("preserves all existing fields that are not part of the partial update", async () => {
    await renderAuth();

    await waitFor(() =>
      expect(screen.getByTestId("isAuthenticated").textContent).toBe("true")
    );

    await act(async () => {
      screen.getByRole("button", { name: "updateUser" }).click();
    });

    await waitFor(() => {
      const user = JSON.parse(screen.getByTestId("user").textContent);
      expect(user.last_name).toBe("Doe");
      expect(user.id).toBe(1);
      expect(user.type).toBe(1);
    });
  });

  it("does nothing when user is null (no crash, state stays null)", async () => {
    // No token → user stays null
    localStorageMock.getItem.mockReturnValue(null);

    const UpdateWhenNull = () => {
      const { updateUser, user } = useAuth();
      return (
        <>
          <span data-testid="user-null">{user === null ? "null" : "set"}</span>
          <button onClick={() => updateUser({ first_name: "X" })}>update-null</button>
        </>
      );
    };

    await act(async () => {
      render(
        <AuthProvider>
          <UpdateWhenNull />
        </AuthProvider>
      );
    });

    await expect(
      act(async () => {
        screen.getByRole("button", { name: "update-null" }).click();
      })
    ).resolves.not.toThrow();

    expect(screen.getByTestId("user-null").textContent).toBe("null");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 7. DERIVED STATE — isAuthenticated & isAdmin
// ════════════════════════════════════════════════════════════════════════════
describe("Derived state", () => {
  it("isAuthenticated is false when user is null", async () => {
    localStorageMock.getItem.mockReturnValue(null);
    await renderAuth();
    expect(screen.getByTestId("isAuthenticated").textContent).toBe("false");
  });

  it("isAuthenticated is true when user is set", async () => {
    localStorageMock.getItem.mockReturnValue("token");
    authAPI.getUser.mockResolvedValueOnce({ data: { id: 1, type: 1 } });
    await renderAuth();
    await waitFor(() =>
      expect(screen.getByTestId("isAuthenticated").textContent).toBe("true")
    );
  });

  it("isAdmin is false when user is null", async () => {
    localStorageMock.getItem.mockReturnValue(null);
    await renderAuth();
    expect(screen.getByTestId("isAdmin").textContent).toBe("false");
  });

  it("isAdmin is false for a regular user (type=1)", async () => {
    localStorageMock.getItem.mockReturnValue("token");
    authAPI.getUser.mockResolvedValueOnce({ data: { id: 1, type: 1 } });
    await renderAuth();
    await waitFor(() =>
      expect(screen.getByTestId("isAdmin").textContent).toBe("false")
    );
  });

  it("isAdmin is true for staff (type=2)", async () => {
    localStorageMock.getItem.mockReturnValue("token");
    authAPI.getUser.mockResolvedValueOnce({ data: { id: 1, type: 2 } });
    await renderAuth();
    await waitFor(() =>
      expect(screen.getByTestId("isAdmin").textContent).toBe("true")
    );
  });

  it("isAdmin is true for superuser (type=3)", async () => {
    localStorageMock.getItem.mockReturnValue("token");
    authAPI.getUser.mockResolvedValueOnce({ data: { id: 1, type: 3 } });
    await renderAuth();
    await waitFor(() =>
      expect(screen.getByTestId("isAdmin").textContent).toBe("true")
    );
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 8. useAuth() outside provider
// ════════════════════════════════════════════════════════════════════════════
describe("useAuth() outside <AuthProvider>", () => {
  it("throws a descriptive error", () => {
    const Orphan = () => {
      useAuth();
      return null;
    };

    // Suppress React's error boundary console noise
    const spy = vi.spyOn(console, "error").mockImplementation(() => { });

    expect(() => render(<Orphan />)).toThrow(
      "useAuth must be used inside <AuthProvider>"
    );

    spy.mockRestore();
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 9. ERROR HANDLING — API failures must not crash the app
// ════════════════════════════════════════════════════════════════════════════
describe("Error handling", () => {
  it("rehydration failure does not crash the app", async () => {
    localStorageMock.getItem.mockReturnValue("bad-token");
    authAPI.getUser.mockRejectedValueOnce(new Error("Network error"));

    await expect(renderAuth()).resolves.not.toThrow();
    expect(screen.getByTestId("loading").textContent).toBe("false");
  });

  it("login failure propagates without crashing the provider", async () => {
    localStorageMock.getItem.mockReturnValue(null);
    authAPI.login.mockRejectedValueOnce(new Error("Wrong password"));

    await renderAuth();

    await expect(
      act(async () => {
        screen.getByRole("button", { name: "login" }).click();
      })
    ).resolves.not.toThrow();

    // State must not have changed
    expect(screen.getByTestId("user").textContent).toBe("null");
    expect(screen.getByTestId("isAuthenticated").textContent).toBe("false");
  });

  it("getUser failure inside login propagates correctly", async () => {
    localStorageMock.getItem.mockReturnValue(null);
    authAPI.login.mockResolvedValueOnce({
      data: { access: "a", refresh: "r" },
    });
    authAPI.getUser.mockRejectedValueOnce(new Error("Server error"));

    let caughtError;
    const ErrorCapture = () => {
      const { login } = useAuth();
      return (
        <button
          onClick={async () => {
            try {
              await login({ email: "a@b.com", password: "pw" });
            } catch (e) {
              caughtError = e;
            }
          }}
        >
          login-getuser-fail
        </button>
      );
    };

    await act(async () => {
      render(
        <AuthProvider>
          <ErrorCapture />
        </AuthProvider>
      );
    });

    await act(async () => {
      screen.getByRole("button", { name: "login-getuser-fail" }).click();
    });

    expect(caughtError).toBeDefined();
    expect(caughtError.message).toBe("Server error");
  });
});
