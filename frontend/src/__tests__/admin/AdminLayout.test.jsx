import { describe, it, test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, within, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AdminLayout from "../../components/admin/AdminLayout";
import { useAuth } from "../../context/AuthContext";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Spy used to track navigation calls triggered via useNavigate()
const mockNavigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("../../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const setWindowWidth = (width) => {
  Object.defineProperty(window, "innerWidth", {
    writable: true,
    configurable: true,
    value: width,
  });
  window.dispatchEvent(new Event("resize"));
};

const renderAdminLayout = () =>
  render(
    <MemoryRouter initialEntries={["/admin"]}>
      <AdminLayout />
    </MemoryRouter>
  );

// The hamburger toggle button is rendered in the header and has no
// accessible name. Since the sidebar (which also contains a button, for
// logout) appears earlier in the DOM than the header, selecting "the first
// button" is unreliable. Target it specifically via its icon class instead.
const getToggleButton = (container) =>
  container.querySelector(".bi-list").closest("button");

const NAV_ITEMS = [
  { label: "Overview", to: "/admin" },
  { label: "Analytics", to: "/admin/analytics" },
  { label: "Orders", to: "/admin/orders" },
  { label: "Products", to: "/admin/products" },
  { label: "Categories", to: "/admin/categories" },
  { label: "Brands", to: "/admin/brands" },
  { label: "Users", to: "/admin/users" },
  { label: "Reviews", to: "/admin/reviews" },
  { label: "Chats", to: "/admin/chat" },
  { label: "Blog", to: "/admin/blog" },
  { label: "Messages", to: "/admin/messages" },
];

describe("AdminLayout", () => {
  const ORIGINAL_INNER_WIDTH = window.innerWidth;
  let logoutMock;

  beforeEach(() => {
    logoutMock = vi.fn().mockResolvedValue(undefined);

    useAuth.mockReturnValue({
      user: { email: "testadmin@example.com" },
      logout: logoutMock,
    });

    mockNavigate.mockClear();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    setWindowWidth(ORIGINAL_INNER_WIDTH);
  });

  // -------------------------------------------------------------------------
  // 1. Rendering
  // -------------------------------------------------------------------------
  describe("Rendering", () => {
    it("renders all navigation links with the correct labels and 'to' paths", () => {
      renderAdminLayout();

      NAV_ITEMS.forEach(({ label, to }) => {
        // There may be two matches (desktop sidebar + hidden mobile sidebar
        // once opened), but on initial render only the desktop sidebar
        // exists, so a single match is expected.
        const link = screen.getByRole("link", { name: new RegExp(label, "i") });
        expect(link).toHaveAttribute("href", to);
      });
    });

    it("renders the 'Back to Store' link pointing to the storefront root", () => {
      renderAdminLayout();

      const backLink = screen.getByRole("link", { name: /back to store/i });
      expect(backLink).toHaveAttribute("href", "/");
    });

    it("does not render the mobile sidebar overlay by default", () => {
      renderAdminLayout();

      // Overview appears once (desktop sidebar) when mobile drawer is closed
      const overviewLinks = screen.getAllByRole("link", { name: /overview/i });
      expect(overviewLinks).toHaveLength(1);
    });
  });

  // -------------------------------------------------------------------------
  // 2. Responsive / state toggles
  // -------------------------------------------------------------------------
  describe("Sidebar toggle behavior", () => {
    it("toggles the collapsed desktop sidebar state when width is >= 1024px", () => {
      setWindowWidth(1280);
      const { container } = renderAdminLayout();

      const toggleButton = getToggleButton(container);
      const adminPanelLabel = screen.getByText("Admin Panel");
      expect(adminPanelLabel).toBeInTheDocument();

      fireEvent.click(toggleButton);

      // When collapsed, the "Admin Panel" text label is no longer rendered
      expect(screen.queryByText("Admin Panel")).not.toBeInTheDocument();

      // Clicking again should restore it
      fireEvent.click(toggleButton);
      expect(screen.getByText("Admin Panel")).toBeInTheDocument();
    });

    it("opens the mobile sidebar drawer when width is < 1024px", () => {
      setWindowWidth(768);
      const { container } = renderAdminLayout();

      // Initially closed: only one "Overview" link rendered (desktop sidebar)
      expect(screen.getAllByRole("link", { name: /overview/i })).toHaveLength(1);

      const toggleButton = getToggleButton(container);
      fireEvent.click(toggleButton);

      // Mobile drawer renders a second copy of the nav (desktop sidebar is
      // hidden via CSS only, so it's still present in the DOM)
      expect(screen.getAllByRole("link", { name: /overview/i })).toHaveLength(2);
    });

    it("closes the mobile sidebar when the backdrop overlay is clicked", () => {
      setWindowWidth(768);
      const { container } = renderAdminLayout();

      const toggleButton = getToggleButton(container);
      fireEvent.click(toggleButton);
      expect(screen.getAllByRole("link", { name: /overview/i })).toHaveLength(2);

      const backdrop = container.querySelector(".bg-black\\/60");
      expect(backdrop).toBeTruthy();
      fireEvent.click(backdrop);

      expect(screen.getAllByRole("link", { name: /overview/i })).toHaveLength(1);
    });

    it("closes the mobile sidebar when a nav link inside it is clicked", () => {
      setWindowWidth(768);
      const { container } = renderAdminLayout();

      const toggleButton = getToggleButton(container);
      fireEvent.click(toggleButton);

      const mobileLinks = screen.getAllByRole("link", { name: /analytics/i });
      // Second instance belongs to the mobile drawer
      fireEvent.click(mobileLinks[mobileLinks.length - 1]);

      expect(screen.getAllByRole("link", { name: /overview/i })).toHaveLength(1);
    });
  });

  // -------------------------------------------------------------------------
  // 3. User details
  // -------------------------------------------------------------------------
  describe("User details", () => {
    it("displays the user's email and avatar initial in the topbar", () => {
      renderAdminLayout();

      const emailMatches = screen.getAllByText("testadmin@example.com");
      expect(emailMatches.length).toBeGreaterThan(0);

      const avatarInitials = screen.getAllByText("T");
      expect(avatarInitials.length).toBeGreaterThan(0);
    });

    it("falls back to 'Admin' and 'A' when no user email is present", () => {
      useAuth.mockReturnValue({
        user: null,
        logout: logoutMock,
      });

      renderAdminLayout();

      expect(screen.getByText("Admin")).toBeInTheDocument();
      expect(screen.getAllByText("A").length).toBeGreaterThan(0);
    });

    it("reflects a different user's email and initial dynamically", () => {
      useAuth.mockReturnValue({
        user: { email: "zara@store.com" },
        logout: logoutMock,
      });

      renderAdminLayout();

      expect(screen.getAllByText("zara@store.com").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Z").length).toBeGreaterThan(0);
    });
  });

  // -------------------------------------------------------------------------
  // 4. Authentication actions
  // -------------------------------------------------------------------------
  describe("Logout / authentication actions", () => {
    it("calls logout and navigates to /login when the desktop logout button is clicked", async () => {
      renderAdminLayout();

      const logoutButton = screen.getByTitle("Log out");
      fireEvent.click(logoutButton);

      expect(logoutMock).toHaveBeenCalledTimes(1);

      // logout() is awaited before navigate() fires, so flush microtasks
      await vi.waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith("/login");
      });
    });

    it("calls logout and navigates to /login from the collapsed sidebar logout button", async () => {
      setWindowWidth(1280);
      const { container } = renderAdminLayout();

      const collapseToggle = getToggleButton(container);
      fireEvent.click(collapseToggle); // collapse sidebar

      // In collapsed mode, the named "Log out" title attribute is removed;
      // locate the logout button via its icon class instead, scoped to this
      // render's container to avoid accidentally matching stray elements.
      const logoutIcon = container.querySelector(".bi-box-arrow-right");
      const logoutButton = logoutIcon.closest("button");

      fireEvent.click(logoutButton);

      expect(logoutMock).toHaveBeenCalledTimes(1);
      await vi.waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith("/login");
      });
    });
  });
});
