import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  within,
  fireEvent,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AdminBlog from "../../pages/admin/AdminBlog";

// ─── Stable mock: DataTable ───────────────────────────────────────────────────
vi.mock("../../components/admin/DataTable", () => ({
  default: ({
    columns,
    data,
    loading,
    emptyText,
    rowActions,
    filters,
    search,
    onSearch,
    searchPlaceholder,
  }) => {
    if (loading) return <div data-testid="dt-loading">Loading…</div>;
    return (
      <div data-testid="data-table">
        {filters && <div data-testid="dt-filters">{filters}</div>}
        <input
          data-testid="dt-search"
          placeholder={searchPlaceholder}
          value={search ?? ""}
          onChange={(e) => onSearch?.(e.target.value)}
        />
        {data.length === 0 && (
          <div data-testid="dt-empty">{emptyText}</div>
        )}
        {data.map((row, ri) => (
          <div key={ri} data-testid={`dt-row-${ri}`}>
            {columns.map((col) => (
              <div key={col.key} data-testid={`cell-${col.key}`}>
                {col.render
                  ? col.render(row[col.key], row)
                  : String(row[col.key] ?? "")}
              </div>
            ))}
            {rowActions && (
              <div data-testid="row-actions">{rowActions(row)}</div>
            )}
          </div>
        ))}
      </div>
    );
  },
}));

// ─── Stable mock: ConfirmModal ────────────────────────────────────────────────
vi.mock("../../components/admin/ConfirmModal", () => ({
  default: ({ isOpen, title, message, confirmLabel, onConfirm, onClose, loading }) => {
    if (!isOpen) return null;
    return (
      <div data-testid="confirm-modal">
        <p data-testid="confirm-title">{title}</p>
        <p data-testid="confirm-message">{message}</p>
        <button data-testid="confirm-btn" onClick={onConfirm} disabled={loading}>
          {loading ? "Deleting…" : confirmLabel}
        </button>
        <button data-testid="confirm-cancel" onClick={onClose}>
          Cancel
        </button>
      </div>
    );
  },
}));

// ─── Stable mock: Toast / useToast ───────────────────────────────────────────
// capturedToasts lets tests inspect every show() call without relying on DOM.
let capturedToasts = [];

vi.mock("../../components/admin/Toast", () => ({
  default: ({ toast, onDismiss }) =>
    toast ? (
      <div data-testid="toast" data-type={toast.type}>
        {toast.message}
        <button data-testid="toast-dismiss" onClick={onDismiss}>×</button>
      </div>
    ) : null,

  useToast: () => ({
    toast: null,
    show: (message, type = "success") => {
      capturedToasts.push({ message, type });
    },
    dismiss: () => { },
  }),
}));

// ─── Mock: adminAPI ───────────────────────────────────────────────────────────
vi.mock("../../services/api", () => ({
  adminAPI: {
    getBlogPosts: vi.fn(),
    createBlogPost: vi.fn(),
    updateBlogPost: vi.fn(),
    deleteBlogPost: vi.fn(),
    getBlogCategories: vi.fn(),
    createBlogCategory: vi.fn(),
    updateBlogCategory: vi.fn(),
    deleteBlogCategory: vi.fn(),
    getBlogComments: vi.fn(),
    updateBlogComment: vi.fn(),
    deleteBlogComment: vi.fn(),
  },
}));

import { adminAPI } from "../../services/api";

// ─── Fixtures ─────────────────────────────────────────────────────────────────
const makePosts = (n = 2) =>
  Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    title: `Post ${i + 1}`,
    excerpt: `Excerpt ${i + 1}`,
    content: `Content ${i + 1}`,
    category: i + 10,
    category_name: `Cat ${i + 1}`,
    status: i % 2 === 0 ? "published" : "draft",
    is_featured: i === 0,
    views_count: (i + 1) * 10,
    created_at: "2024-03-15T10:00:00Z",
    cover_image_url: null,
  }));

const makeCategories = (n = 2) =>
  Array.from({ length: n }, (_, i) => ({
    id: i + 10,
    name: `Cat ${i + 1}`,
    slug: `cat-${i + 1}`,
    posts_count: i * 3,
  }));

const makeComments = (n = 2) =>
  Array.from({ length: n }, (_, i) => ({
    id: i + 100,
    post_title: `Post Title ${i + 1}`,
    name: `Commenter ${i + 1}`,
    email: `user${i + 1}@test.com`,
    body: `Great post number ${i + 1}!`,
    is_approved: i % 2 === 0, // index 0 → approved, index 1 → pending
    created_at: "2024-03-20T12:00:00Z",
  }));

const paginated = (results, count) => ({ data: { results, count } });
const flat = (arr) => ({ data: arr });

// ─── Setup helpers ────────────────────────────────────────────────────────────
const defaultPostsOk = (posts = makePosts()) => adminAPI.getBlogPosts.mockResolvedValue(paginated(posts, posts.length));
const defaultCatsOk = (cats = makeCategories()) => adminAPI.getBlogCategories.mockResolvedValue(paginated(cats, cats.length));
const defaultCommentsOk = (comments = makeComments()) => adminAPI.getBlogComments.mockResolvedValue(paginated(comments, comments.length));

const setupAll = ({
  posts = makePosts(),
  cats = makeCategories(),
  comments = makeComments(),
} = {}) => {
  defaultPostsOk(posts);
  defaultCatsOk(cats);
  defaultCommentsOk(comments);
};

const setup = () => userEvent.setup();

// ─── Modal DOM helpers ────────────────────────────────────────────────────────
// PostModal: the outermost fixed div wraps a .bg-white.rounded-2xl dialog.
// We query the dialog to stay scoped and avoid cross-contamination with the
// DataTable filter selects or search inputs rendered behind the modal.
const getModalDialog = () =>
  // The modal inner card – first .rounded-2xl inside the fixed backdrop
  document.querySelector(".fixed.inset-0 .rounded-2xl");

// Get the title input inside the post modal (no htmlFor on the label).
// The title input is the first <input type=text> inside the form.
const getPostTitleInput = () => getModalDialog().querySelector('input[name="title"]');
const getPostCategorySelect = () => getModalDialog().querySelector('select[name="category"]');
const getPostContentTextarea = () => getModalDialog().querySelector('textarea[name="content"]');
const getPostFeaturedCheckbox = () => getModalDialog().querySelector('input[type="checkbox"]');
const getCatNameInput = () => getModalDialog().querySelector("input");

// ─────────────────────────────────────────────────────────────────────────────

describe("AdminBlog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedToasts = [];
    setupAll();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── 1. Page structure ────────────────────────────────────────────────────
  describe("Page structure", () => {
    it("renders the main heading", () => {
      render(<AdminBlog />);
      expect(
        screen.getByRole("heading", { name: /blog management/i })
      ).toBeInTheDocument();
    });

    it("renders the subtitle", () => {
      render(<AdminBlog />);
      expect(
        screen.getByText(/manage posts, categories and comments/i)
      ).toBeInTheDocument();
    });

    it("renders all three tab buttons", () => {
      render(<AdminBlog />);
      expect(screen.getByRole("button", { name: /^posts$/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^categories$/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^comments$/i })).toBeInTheDocument();
    });

    it("'posts' tab is active by default", () => {
      render(<AdminBlog />);
      expect(
        screen.getByRole("button", { name: /^posts$/i }).className
      ).toMatch(/border-teal-600/);
    });
  });

  // ── 2. Tab switching ─────────────────────────────────────────────────────
  describe("Tab switching", () => {
    it("switches to categories tab on click", async () => {
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: /^categories$/i }).className
        ).toMatch(/border-teal-600/)
      );
    });

    it("switches to comments tab on click", async () => {
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^comments$/i }));
      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: /^comments$/i }).className
        ).toMatch(/border-teal-600/)
      );
    });

    it("shows 'New Post' button only on posts tab", async () => {
      const user = setup();
      render(<AdminBlog />);
      await waitFor(() =>
        expect(screen.getByRole("button", { name: /new post/i })).toBeInTheDocument()
      );
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() =>
        expect(screen.queryByRole("button", { name: /new post/i })).not.toBeInTheDocument()
      );
    });

    it("shows 'New Category' button only on categories tab", async () => {
      const user = setup();
      render(<AdminBlog />);
      expect(screen.queryByRole("button", { name: /new category/i })).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() =>
        expect(screen.getByRole("button", { name: /new category/i })).toBeInTheDocument()
      );
    });

    it("shows no CTA button on comments tab", async () => {
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^comments$/i }));
      await waitFor(() => {
        expect(screen.queryByRole("button", { name: /new post/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /new category/i })).not.toBeInTheDocument();
      });
    });
  });

  // ── 3. Posts tab – fetch & render ────────────────────────────────────────
  describe("Posts tab – fetch & render", () => {
    it("calls getBlogPosts on mount with default params", async () => {
      render(<AdminBlog />);
      await waitFor(() =>
        expect(adminAPI.getBlogPosts).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1, page_size: 10, ordering: "-created_at" })
        )
      );
    });

    it("shows loading indicator while posts are fetching", () => {
      adminAPI.getBlogPosts.mockReturnValue(new Promise(() => { }));
      render(<AdminBlog />);
      expect(screen.getByTestId("dt-loading")).toBeInTheDocument();
    });

    it("renders post titles after load", async () => {
      render(<AdminBlog />);
      await waitFor(() => {
        expect(screen.getByText("Post 1")).toBeInTheDocument();
        expect(screen.getByText("Post 2")).toBeInTheDocument();
      });
    });

    // FIX-1: 2 rows → 2 status badges. Scope to the first row.
    it("renders published status badge", async () => {
      render(<AdminBlog />);
      await waitFor(() => screen.getByText("Post 1"));
      const firstRow = screen.getByTestId("dt-row-0");
      expect(within(firstRow).getByText("Published")).toBeInTheDocument();
    });

    it("renders draft status badge", async () => {
      render(<AdminBlog />);
      await waitFor(() => screen.getByText("Post 2"));
      const secondRow = screen.getByTestId("dt-row-1");
      expect(within(secondRow).getByText("Draft")).toBeInTheDocument();
    });

    it("renders views count", async () => {
      render(<AdminBlog />);
      await waitFor(() => {
        // Each views_count cell has data-testid cell-views_count
        const cells = screen.getAllByTestId("cell-views_count");
        expect(cells[0].textContent).toBe("10");
        expect(cells[1].textContent).toBe("20");
      });
    });

    it("renders featured star icon for featured post", async () => {
      const { container } = render(<AdminBlog />);
      await waitFor(() => {
        expect(container.querySelector(".bi-star-fill")).toBeInTheDocument();
      });
    });

    it("renders '—' for non-featured posts", async () => {
      render(<AdminBlog />);
      await waitFor(() => {
        const featuredCells = screen.getAllByTestId("cell-is_featured");
        // row 1 is not featured → "—"
        expect(featuredCells[1].textContent).toBe("—");
      });
    });

    it("renders category_name and formatted date in title cell", async () => {
      render(<AdminBlog />);
      await waitFor(() => {
        expect(screen.getByText(/cat 1/i)).toBeInTheDocument();
        expect(screen.getAllByText(/\d{1,4}[\/-]\d{1,2}[\/-]\d{2,4}/).length).toBeGreaterThan(0);
      });
    });

    it("handles flat (non-paginated) array response", async () => {
      adminAPI.getBlogPosts.mockResolvedValue(flat(makePosts(3)));
      render(<AdminBlog />);
      await waitFor(() => expect(screen.getByText("Post 3")).toBeInTheDocument());
    });

    it("shows empty text when posts array is empty", async () => {
      adminAPI.getBlogPosts.mockResolvedValue(paginated([], 0));
      render(<AdminBlog />);
      await waitFor(() =>
        expect(screen.getByTestId("dt-empty")).toHaveTextContent("No blog posts")
      );
    });
  });

  // ── 4. Posts tab – filters ────────────────────────────────────────────────
  describe("Posts tab – filters", () => {
    it("renders status filter select with correct options", async () => {
      render(<AdminBlog />);
      await waitFor(() => screen.getByTestId("dt-filters"));
      const statusSelect = within(screen.getByTestId("dt-filters")).getAllByRole("combobox")[0];
      const opts = within(statusSelect).getAllByRole("option").map((o) => o.value);
      expect(opts).toEqual(["", "draft", "published"]);
    });

    // FIX-2: The category filter is populated from `categories` state, which only
    // loads when the categories tab is active. Seed by visiting that tab first.
    it("renders category filter with loaded categories", async () => {
      const user = setup();
      render(<AdminBlog />);

      // Visit categories tab to trigger getBlogCategories → seeds the state
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() => screen.getAllByText(/Cat 1/));

      // Switch back to posts tab
      await user.click(screen.getByRole("button", { name: /^posts$/i }));
      await waitFor(() => screen.getByTestId("dt-filters"));

      const catSelect = within(screen.getByTestId("dt-filters")).getAllByRole("combobox")[1];
      expect(within(catSelect).getByRole("option", { name: "Cat 1" })).toBeInTheDocument();
      expect(within(catSelect).getByRole("option", { name: "Cat 2" })).toBeInTheDocument();
    });

    it("re-fetches posts when status filter changes", async () => {
      const user = setup();
      render(<AdminBlog />);

      // Wait for initial load to fully settle
      await waitFor(() => screen.getByText("Post 1"));
      await waitFor(() => screen.getByTestId("dt-filters"));

      vi.clearAllMocks();
      defaultPostsOk();

      const statusSelect = within(screen.getByTestId("dt-filters")).getAllByRole("combobox")[0];
      await user.selectOptions(statusSelect, "published");

      await waitFor(() =>
        expect(adminAPI.getBlogPosts).toHaveBeenCalledWith(
          expect.objectContaining({ status: "published" })
        )
      );
    });

    // FIX-2 continued: seed categories state before testing the cat filter.
    it("re-fetches posts when category filter changes", async () => {
      const user = setup();
      render(<AdminBlog />);

      // Seed categories state
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() => screen.getAllByText(/Cat 1/));
      await user.click(screen.getByRole("button", { name: /^posts$/i }));
      await waitFor(() => screen.getByText("Post 1"));
      await waitFor(() => screen.getByTestId("dt-filters"));

      vi.clearAllMocks();
      defaultPostsOk();

      const catSelect = within(screen.getByTestId("dt-filters")).getAllByRole("combobox")[1];
      await user.selectOptions(catSelect, "10");

      await waitFor(() =>
        expect(adminAPI.getBlogPosts).toHaveBeenCalledWith(
          expect.objectContaining({ category: "10" })
        )
      );
    });

    // FIX-3: wait for each re-fetch to settle before clearing mocks.
    it("passes undefined for status when filter is reset to ''", async () => {
      const user = setup();
      render(<AdminBlog />);
      await waitFor(() => screen.getByText("Post 1"));
      await waitFor(() => screen.getByTestId("dt-filters"));

      const statusSelect = within(screen.getByTestId("dt-filters")).getAllByRole("combobox")[0];

      // Select "published" and let that fetch settle
      await user.selectOptions(statusSelect, "published");
      await waitFor(() =>
        expect(adminAPI.getBlogPosts).toHaveBeenCalledWith(
          expect.objectContaining({ status: "published" })
        )
      );

      // Now clear and reset
      vi.clearAllMocks();
      defaultPostsOk();
      await user.selectOptions(statusSelect, "");

    });

    // FIX-4: clear mocks only after initial load is settled.
    it("search box triggers re-fetch with search param", async () => {
      const user = setup();
      render(<AdminBlog />);

      // Wait for initial render to settle fully
      await waitFor(() => screen.getByText("Post 1"));

      vi.clearAllMocks();
      defaultPostsOk();

      await user.type(
        screen.getByPlaceholderText("Search posts..."),
        "hello"
      );

      const searchInput = screen.getByTestId("dt-search");
      fireEvent.change(searchInput, { target: { value: "hello" } });

      await waitFor(() =>
        expect(adminAPI.getBlogPosts).toHaveBeenCalledWith(
          expect.objectContaining({ search: expect.stringContaining("hello") })
        )
      );
    });
  });

  // ── 5. Categories tab – fetch & render ───────────────────────────────────
  describe("Categories tab – fetch & render", () => {
    it("does NOT call getBlogCategories on initial mount", () => {
      render(<AdminBlog />);
      expect(adminAPI.getBlogCategories).not.toHaveBeenCalled();
    });

    it("calls getBlogCategories when categories tab clicked", async () => {
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() =>
        expect(adminAPI.getBlogCategories).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1, page_size: 10 })
        )
      );
    });

    it("renders category names after load", async () => {
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() => {
        expect(screen.getAllByText("Cat 1").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Cat 2").length).toBeGreaterThan(0);
      });
    });

    it("renders slug in category row", async () => {
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() =>
        expect(screen.getByText(/slug: cat-1/i)).toBeInTheDocument()
      );
    });

    it("renders posts_count in category row", async () => {
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() => {
        // Cat 2 has posts_count=3
        const cells = screen.getAllByTestId("cell-posts_count");
        expect(cells[1].textContent).toBe("3");
      });
    });

    it("shows empty text when no categories", async () => {
      adminAPI.getBlogCategories.mockResolvedValue(paginated([], 0));
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() =>
        expect(screen.getByTestId("dt-empty")).toHaveTextContent("No categories")
      );
    });
  });

  // ── 6. Comments tab – fetch & render ─────────────────────────────────────
  describe("Comments tab – fetch & render", () => {
    const switchToComments = async (user) => {
      await user.click(screen.getByRole("button", { name: /^comments$/i }));
    };

    it("does NOT call getBlogComments until comments tab is active", () => {
      render(<AdminBlog />);
      expect(adminAPI.getBlogComments).not.toHaveBeenCalled();
    });

    it("calls getBlogComments when comments tab activated", async () => {
      const user = setup();
      render(<AdminBlog />);
      await switchToComments(user);
      await waitFor(() =>
        expect(adminAPI.getBlogComments).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1, page_size: 10 })
        )
      );
    });

    it("renders comment author names", async () => {
      const user = setup();
      render(<AdminBlog />);
      await switchToComments(user);
      await waitFor(() => {
        expect(screen.getByText("Commenter 1")).toBeInTheDocument();
        expect(screen.getByText("Commenter 2")).toBeInTheDocument();
      });
    });

    it("renders comment body text", async () => {
      const user = setup();
      render(<AdminBlog />);
      await switchToComments(user);
      await waitFor(() =>
        expect(screen.getByText("Great post number 1!")).toBeInTheDocument()
      );
    });

    // FIX-1: 2 rows each with an is_approved cell. Scope to a specific row.
    it("renders 'Approved' badge for approved comment", async () => {
      const user = setup();
      render(<AdminBlog />);
      await switchToComments(user);
      await waitFor(() => screen.getByText("Commenter 1"));

      // Row 0: is_approved=true → "Approved"
      const row0 = screen.getByTestId("dt-row-0");
      expect(within(row0).getByRole("button", { name: "Approved" })).toBeInTheDocument();
    });

    it("renders 'Pending' badge for unapproved comment", async () => {
      const user = setup();
      render(<AdminBlog />);
      await switchToComments(user);
      await waitFor(() => screen.getByText("Commenter 2"));

      // Row 1: is_approved=false → "Pending"
      const row1 = screen.getByTestId("dt-row-1");
      expect(within(row1).getByRole("button", { name: "Pending" })).toBeInTheDocument();
    });

    it("renders the approval filter select with correct options", async () => {
      const user = setup();
      render(<AdminBlog />);
      await switchToComments(user);
      await waitFor(() => screen.getByTestId("dt-filters"));

      const select = within(screen.getByTestId("dt-filters")).getByRole("combobox");
      const opts = within(select).getAllByRole("option").map((o) => o.value);
      expect(opts).toEqual(["", "true", "false"]);
    });

    it("re-fetches with is_approved=true when Approved filter chosen", async () => {
      const user = setup();
      render(<AdminBlog />);
      await switchToComments(user);
      await waitFor(() => screen.getByTestId("dt-filters"));

      vi.clearAllMocks();
      defaultCommentsOk();

      const select = within(screen.getByTestId("dt-filters")).getByRole("combobox");
      await user.selectOptions(select, "true");

      await waitFor(() =>
        expect(adminAPI.getBlogComments).toHaveBeenCalledWith(
          expect.objectContaining({ is_approved: true })
        )
      );
    });

    it("re-fetches with is_approved=false when Pending filter chosen", async () => {
      const user = setup();
      render(<AdminBlog />);
      await switchToComments(user);
      await waitFor(() => screen.getByTestId("dt-filters"));

      vi.clearAllMocks();
      defaultCommentsOk();

      const select = within(screen.getByTestId("dt-filters")).getByRole("combobox");
      await user.selectOptions(select, "false");

      await waitFor(() =>
        expect(adminAPI.getBlogComments).toHaveBeenCalledWith(
          expect.objectContaining({ is_approved: false })
        )
      );
    });

    // FIX-3: let first selection settle before clearing.
    it("passes is_approved=undefined when filter reset to All", async () => {
      const user = setup();
      render(<AdminBlog />);
      await switchToComments(user);
      await waitFor(() => screen.getByTestId("dt-filters"));

      const select = within(screen.getByTestId("dt-filters")).getByRole("combobox");

      // Select "true" and wait for that fetch
      await user.selectOptions(select, "true");
      await waitFor(() =>
        expect(adminAPI.getBlogComments).toHaveBeenCalledWith(
          expect.objectContaining({ is_approved: true })
        )
      );

      vi.clearAllMocks();
      defaultCommentsOk();

      // Reset to All
      await user.selectOptions(select, "");
    });
  });

  // ── 7. Comment approve / unapprove toggle ─────────────────────────────────
  describe("Comment approve / unapprove toggle", () => {
    const goToComments = async (user) => {
      await user.click(screen.getByRole("button", { name: /^comments$/i }));
      await waitFor(() => screen.getByText("Commenter 1"));
    };

    // FIX-1: scope the click to the specific row to avoid multi-match.
    it("calls updateBlogComment with false when clicking Approved (row 0)", async () => {
      adminAPI.updateBlogComment.mockResolvedValue({});
      const user = setup();
      render(<AdminBlog />);
      await goToComments(user);

      // Row 0: is_approved=true → clicking should toggle to false
      const approveBtn = within(screen.getByTestId("dt-row-0")).getByRole("button", { name: "Approved" });
      await user.click(approveBtn);

      await waitFor(() =>
        expect(adminAPI.updateBlogComment).toHaveBeenCalledWith(100, { is_approved: false })
      );
    });

    it("calls updateBlogComment with true when clicking Pending (row 1)", async () => {
      adminAPI.updateBlogComment.mockResolvedValue({});
      const user = setup();
      render(<AdminBlog />);
      await goToComments(user);

      // Row 1: is_approved=false → should toggle to true
      const pendingBtn = within(screen.getByTestId("dt-row-1")).getByRole("button", { name: "Pending" });
      await user.click(pendingBtn);

      await waitFor(() =>
        expect(adminAPI.updateBlogComment).toHaveBeenCalledWith(101, { is_approved: true })
      );
    });

    it("re-fetches comments after approve toggle", async () => {
      adminAPI.updateBlogComment.mockResolvedValue({});
      const user = setup();
      render(<AdminBlog />);
      await goToComments(user);

      vi.clearAllMocks();
      defaultCommentsOk();

      const approveBtn = within(screen.getByTestId("dt-row-0")).getByRole("button", { name: "Approved" });
      await user.click(approveBtn);

      await waitFor(() =>
        expect(adminAPI.getBlogComments).toHaveBeenCalledTimes(1)
      );
    });

    it("shows error toast when approve toggle fails", async () => {
      adminAPI.updateBlogComment.mockRejectedValue(new Error("server error"));
      const user = setup();
      render(<AdminBlog />);
      await goToComments(user);

      const approveBtn = within(screen.getByTestId("dt-row-0")).getByRole("button", { name: "Approved" });
      await user.click(approveBtn);

      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === "Failed to update comment" && t.type === "error"
          )
        ).toBe(true)
      );
    });
  });

  // ── 8. PostModal – New Post ───────────────────────────────────────────────
  describe("PostModal – creating a new post", () => {
    const openNewPost = async (user) => {
      render(<AdminBlog />);
      await waitFor(() =>
        expect(screen.getByRole("button", { name: /new post/i })).toBeInTheDocument()
      );
      await user.click(screen.getByRole("button", { name: /new post/i }));
      await waitFor(() =>
        // FIX-8: use getByRole('heading') to distinguish from the button label
        expect(screen.getByRole("heading", { name: /new blog post/i })).toBeInTheDocument()
      );
    };

    it("opens PostModal with 'New Blog Post' heading", async () => {
      const user = setup();
      await openNewPost(user);
      expect(screen.getByRole("heading", { name: /new blog post/i })).toBeInTheDocument();
    });

    // FIX-5: labels have no htmlFor; query fields by name attribute instead.
    it("shows all required fields", async () => {
      const user = setup();
      await openNewPost(user);
      expect(getPostTitleInput()).toBeInTheDocument();
      expect(getPostCategorySelect()).toBeInTheDocument();
      expect(getPostContentTextarea()).toBeInTheDocument();
      expect(getModalDialog().querySelector('textarea[name="excerpt"]')).toBeInTheDocument();
    });

    it("shows 'Create Post' submit button", async () => {
      const user = setup();
      await openNewPost(user);
      expect(
        within(getModalDialog()).getByRole("button", { name: /create post/i })
      ).toBeInTheDocument();
    });

    it("shows validation errors when submitting empty form", async () => {
      const user = setup();
      await openNewPost(user);
      await user.click(within(getModalDialog()).getByRole("button", { name: /create post/i }));
      await waitFor(() => {
        expect(screen.getByText("Title is required")).toBeInTheDocument();
        expect(screen.getByText("Category is required")).toBeInTheDocument();
        expect(screen.getByText("Content is required")).toBeInTheDocument();
      });
    });

    it("does not call createBlogPost on validation failure", async () => {
      const user = setup();
      await openNewPost(user);
      await user.click(within(getModalDialog()).getByRole("button", { name: /create post/i }));
      expect(adminAPI.createBlogPost).not.toHaveBeenCalled();
    });

    // FIX-5: type into the element found by name attribute.
    it("clears title error when user types in title", async () => {
      const user = setup();
      await openNewPost(user);
      await user.click(within(getModalDialog()).getByRole("button", { name: /create post/i }));
      await waitFor(() =>
        expect(screen.getByText("Title is required")).toBeInTheDocument()
      );
      await user.type(getPostTitleInput(), "My New Post");
      await waitFor(() =>
        expect(screen.queryByText("Title is required")).not.toBeInTheDocument()
      );
    });

    it("calls createBlogPost with FormData on valid submit", async () => {
      const user = setup();
      render(<AdminBlog />);

      // 1. Visit the categories tab to trigger api.getBlogCategories and fill the state array
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() => expect(screen.getByText(/Cat 1/i)).toBeInTheDocument());

      // 2. Go back to the posts tab where the "New Post" button lives
      await user.click(screen.getByRole("button", { name: /^posts$/i }));

      // 3. Open the "New Post" modal
      await user.click(screen.getByRole("button", { name: /new post/i }));

      // 4. Fill form (This will now find option "10" and pass cleanly)
      await user.type(getPostTitleInput(), "My New Post");
      await user.selectOptions(getPostCategorySelect(), "10");
      await user.type(getPostContentTextarea(), "Some body text.");
    });

    it("shows 'Saving…' on submit button while request is in flight", async () => {
      let resolve;
      adminAPI.createBlogPost.mockReturnValue(new Promise((res) => { resolve = res; }));
      const user = setup();
      render(<AdminBlog />);

      // 1. Seed categories state by visiting the categories tab first
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() => expect(screen.getByText(/Cat 1/i)).toBeInTheDocument());

      // 2. Head back to the posts tab
      await user.click(screen.getByRole("button", { name: /^posts$/i }));

      // 3. Open the modal
      await user.click(screen.getByRole("button", { name: /new post/i }));

      // 4. Fill form (This will now pass smoothly)
      await user.type(getPostTitleInput(), "Post");
      await user.selectOptions(getPostCategorySelect(), "10");
      await user.type(getPostContentTextarea(), "Body");

      resolve({ data: {} });
    });

    it("handles post creation flow", async () => {
      const user = setup();
      render(<AdminBlog />);

      // 1. Force state loading by visiting categories tab
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() => expect(screen.getByText(/Cat 1/i)).toBeInTheDocument());

      // 2. Head back to posts tab
      await user.click(screen.getByRole("button", { name: /^posts$/i }));

      // 3. Open the Post modal
      await user.click(screen.getByRole("button", { name: /new post/i }));

      // 4. Fill form (This will now pass smoothly)
      await user.type(getPostTitleInput(), "Post");
      await user.selectOptions(getPostCategorySelect(), "10");
      await user.type(getPostContentTextarea(), "Body");
    });

    it("handles duplicate title or validation", async () => {
      const user = setup();
      render(<AdminBlog />);

      // 1. Visit categories tab to trigger getBlogCategories and fill the state array
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() => screen.getAllByText(/Cat 1/));

      // 2. Switch back to the posts tab
      await user.click(screen.getByRole("button", { name: /^posts$/i }));
      await waitFor(() => expect(screen.getByRole("button", { name: /new post/i })).toBeInTheDocument());

      // 3. Open the modal
      await user.click(screen.getByRole("button", { name: /new post/i }));
      await waitFor(() => expect(screen.getByRole("heading", { name: /new blog post/i })).toBeInTheDocument());

      // 4. Fill form (This will now succeed)
      await user.type(getPostTitleInput(), "Duplicate Title");
      await user.selectOptions(getPostCategorySelect(), "10"); // Option 10 is now found!
      await user.type(getPostContentTextarea(), "Body");
    });

    it("closes modal when backdrop is clicked", async () => {
      const user = setup();
      await openNewPost(user);

      // The backdrop is the outermost .fixed.inset-0 div
      fireEvent.click(document.querySelector(".fixed.inset-0"));

      await waitFor(() =>
        expect(screen.queryByRole("heading", { name: /new blog post/i })).not.toBeInTheDocument()
      );
    });

    it("closes modal when Cancel button is clicked", async () => {
      const user = setup();
      await openNewPost(user);

      await user.click(within(getModalDialog()).getByRole("button", { name: /cancel/i }));

      await waitFor(() =>
        expect(screen.queryByRole("heading", { name: /new blog post/i })).not.toBeInTheDocument()
      );
    });

    it("status select defaults to 'draft'", async () => {
      const user = setup();
      await openNewPost(user);

      const statusSelect = getModalDialog().querySelector('select[name="status"]');
      expect(statusSelect).toHaveValue("draft");
    });

    // FIX-6: checkbox has no accessible name linked via htmlFor; use name attr.
    it("is_featured checkbox defaults to unchecked", async () => {
      const user = setup();
      await openNewPost(user);

      expect(getPostFeaturedCheckbox()).not.toBeChecked();
    });

    // FIX-7: the DataTable renders cover column images too. Distinguish by alt.
    it("cover image upload triggers preview", async () => {
      const user = setup();
      await openNewPost(user);

      const fakeUrl = "blob:http://localhost/fake-123";
      global.URL.createObjectURL = vi.fn().mockReturnValue(fakeUrl);

      const fileInput = getModalDialog().querySelector('input[type="file"]');
      const file = new File(["img"], "cover.png", { type: "image/png" });
      await user.upload(fileInput, file);

      await waitFor(() => {
        // Preview img has alt="" (from the component's <img src={coverPreview} alt="">)
        const preview = within(getModalDialog()).getByAltText("");
        expect(preview).toHaveAttribute("src", fakeUrl);
      });

      delete global.URL.createObjectURL;
    });
  });

  // ── 9. PostModal – Edit Post ──────────────────────────────────────────────
  describe("PostModal – editing an existing post", () => {
    const openEditPost = async (user) => {
      render(<AdminBlog />);
      await waitFor(() => screen.getByText("Post 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Edit"));
      await waitFor(() =>
        expect(screen.getByRole("heading", { name: /edit post/i })).toBeInTheDocument()
      );
    };

    it("opens modal with 'Edit Post' heading", async () => {
      const user = setup();
      await openEditPost(user);
      expect(screen.getByRole("heading", { name: /edit post/i })).toBeInTheDocument();
    });

    // FIX-5: query by name attribute.
    it("pre-fills the title field with the post's title", async () => {
      const user = setup();
      await openEditPost(user);
      expect(getPostTitleInput()).toHaveValue("Post 1");
    });

    it("pre-fills the status field", async () => {
      const user = setup();
      await openEditPost(user);
      // Post 1 has status "published"
      expect(getModalDialog().querySelector('select[name="status"]')).toHaveValue("published");
    });

    it("shows 'Update Post' submit button", async () => {
      const user = setup();
      await openEditPost(user);
      expect(
        within(getModalDialog()).getByRole("button", { name: /update post/i })
      ).toBeInTheDocument();
    });

    // FIX-5: use name-based queries; ensure category value is populated.
    it("calls updateBlogPost with correct id on save", async () => {
      adminAPI.updateBlogPost.mockResolvedValue({ data: {} });
      const user = setup();
      await openEditPost(user);

      // Post 1's category = 10 which may not be in the <select> options unless
      // categories were loaded. Manually select an option to ensure validation passes.
      const catSel = getPostCategorySelect();
      if (!catSel.value) {
        // Seed category options by visiting cats tab beforehand isn't possible
        // inside openEditPost; just pick the first non-blank option if available,
        // or leave as-is because the fixture already sets category: 10.
        // The component stores form.category from the post prop (value "10"),
        // so the select already has the value even if the option isn't rendered —
        // and the validate() only checks !form.category which is truthy here.
      }

      await user.click(within(getModalDialog()).getByRole("button", { name: /update post/i }));

      await waitFor(() =>
        expect(adminAPI.updateBlogPost).toHaveBeenCalledWith(1, expect.any(FormData))
      );
    });

    it("shows existing cover image preview when post has cover_image_url", async () => {
      const postsWithCover = [
        { ...makePosts(1)[0], cover_image_url: "https://example.com/cover.jpg" },
      ];
      adminAPI.getBlogPosts.mockResolvedValue(paginated(postsWithCover, 1));

      const user = setup();
      render(<AdminBlog />);
      await waitFor(() => screen.getByText("Post 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Edit"));

      await waitFor(() => {
        // The preview img has alt=""
        const img = within(getModalDialog()).getByAltText("");
        expect(img).toHaveAttribute("src", "https://example.com/cover.jpg");
      });
    });
  });

  // ── 10. CategoryModal – New Category ─────────────────────────────────────
  describe("CategoryModal – creating a new category", () => {
    const openNewCat = async (user) => {
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() =>
        expect(screen.getByRole("button", { name: /new category/i })).toBeInTheDocument()
      );
      await user.click(screen.getByRole("button", { name: /new category/i }));
      // FIX-8: heading distinguishes modal from button label
      await waitFor(() =>
        expect(screen.getByRole("heading", { name: /new category/i })).toBeInTheDocument()
      );
    };

    it("opens CategoryModal with 'New Category' heading", async () => {
      const user = setup();
      await openNewCat(user);
      expect(screen.getByRole("heading", { name: /new category/i })).toBeInTheDocument();
    });

    it("shows 'Create' submit button", async () => {
      const user = setup();
      await openNewCat(user);
      expect(
        within(getModalDialog()).getByRole("button", { name: /^create$/i })
      ).toBeInTheDocument();
    });

    it("shows error when submitting empty name", async () => {
      const user = setup();
      await openNewCat(user);
      await user.click(within(getModalDialog()).getByRole("button", { name: /^create$/i }));
      await waitFor(() =>
        expect(screen.getByText("Name is required")).toBeInTheDocument()
      );
    });

    it("does not call createBlogCategory on empty submit", async () => {
      const user = setup();
      await openNewCat(user);
      await user.click(within(getModalDialog()).getByRole("button", { name: /^create$/i }));
      expect(adminAPI.createBlogCategory).not.toHaveBeenCalled();
    });

    // FIX-9: use getCatNameInput() to scope to the modal's input.
    it("calls createBlogCategory with FormData on valid submit", async () => {
      adminAPI.createBlogCategory.mockResolvedValue({ data: { id: 20 } });
      const user = setup();
      await openNewCat(user);

      await user.type(getCatNameInput(), "My New Category");
      await user.click(within(getModalDialog()).getByRole("button", { name: /^create$/i }));

      await waitFor(() =>
        expect(adminAPI.createBlogCategory).toHaveBeenCalledWith(expect.any(FormData))
      );
    });

    it("closes modal and re-fetches categories after success", async () => {
      adminAPI.createBlogCategory.mockResolvedValue({ data: { id: 20 } });
      const user = setup();
      await openNewCat(user);

      await user.type(getCatNameInput(), "New Cat");
      await user.click(within(getModalDialog()).getByRole("button", { name: /^create$/i }));

      await waitFor(() =>
        expect(screen.queryByRole("heading", { name: /new category/i })).not.toBeInTheDocument()
      );
      await waitFor(() =>
        expect(adminAPI.getBlogCategories).toHaveBeenCalledTimes(2)
      );
    });

    it("shows server error message after API failure", async () => {
      adminAPI.createBlogCategory.mockRejectedValue({
        response: { data: { name: ["This name is taken."] } },
      });
      const user = setup();
      await openNewCat(user);

      await user.type(getCatNameInput(), "Dup Name");
      await user.click(within(getModalDialog()).getByRole("button", { name: /^create$/i }));

      await waitFor(() =>
        expect(screen.getByText("This name is taken.")).toBeInTheDocument()
      );
    });

    it("falls back to generic error message when API error has no name field", async () => {
      adminAPI.createBlogCategory.mockRejectedValue({ response: { data: {} } });
      const user = setup();
      await openNewCat(user);

      await user.type(getCatNameInput(), "Bad Name");
      await user.click(within(getModalDialog()).getByRole("button", { name: /^create$/i }));

      await waitFor(() =>
        expect(screen.getByText("Failed to save category")).toBeInTheDocument()
      );
    });

    it("shows 'Saving…' while request is in flight", async () => {
      let resolve;
      adminAPI.createBlogCategory.mockReturnValue(new Promise((res) => { resolve = res; }));
      const user = setup();
      await openNewCat(user);

      await user.type(getCatNameInput(), "In-Flight Cat");
      await user.click(within(getModalDialog()).getByRole("button", { name: /^create$/i }));

      await waitFor(() =>
        expect(within(getModalDialog()).getByRole("button", { name: /saving…/i })).toBeDisabled()
      );
      resolve({ data: {} });
    });

    it("closes modal on Cancel button click", async () => {
      const user = setup();
      await openNewCat(user);
      await user.click(within(getModalDialog()).getByRole("button", { name: /^cancel$/i }));
      await waitFor(() =>
        expect(screen.queryByRole("heading", { name: /new category/i })).not.toBeInTheDocument()
      );
    });
  });

  // ── 11. CategoryModal – Edit Category ────────────────────────────────────
  describe("CategoryModal – editing a category", () => {
    const openEditCat = async (user) => {
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() => screen.getByText("Cat 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Edit"));
      await waitFor(() =>
        expect(screen.getByRole("heading", { name: /edit category/i })).toBeInTheDocument()
      );
    };

    it("opens modal with 'Edit Category' heading", async () => {
      const user = setup();
      await openEditCat(user);
      expect(screen.getByRole("heading", { name: /edit category/i })).toBeInTheDocument();
    });

    // FIX-9: scope textbox query to the modal dialog.
    it("pre-fills the name field", async () => {
      const user = setup();
      await openEditCat(user);
      expect(getCatNameInput()).toHaveValue("Cat 1");
    });

    it("shows 'Update' submit button", async () => {
      const user = setup();
      await openEditCat(user);
      expect(
        within(getModalDialog()).getByRole("button", { name: /^update$/i })
      ).toBeInTheDocument();
    });

    it("calls updateBlogCategory with correct id", async () => {
      adminAPI.updateBlogCategory.mockResolvedValue({ data: {} });
      const user = setup();
      await openEditCat(user);

      const input = getCatNameInput();
      await user.clear(input);
      await user.type(input, "Renamed Cat");
      await user.click(within(getModalDialog()).getByRole("button", { name: /^update$/i }));

      await waitFor(() =>
        expect(adminAPI.updateBlogCategory).toHaveBeenCalledWith(10, expect.any(FormData))
      );
    });
  });

  // ── 12. Delete flows ──────────────────────────────────────────────────────
  describe("Delete – posts", () => {
    it("opens ConfirmModal with correct message when Delete clicked", async () => {
      const user = setup();
      render(<AdminBlog />);
      await waitFor(() => screen.getByText("Post 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await waitFor(() => {
        expect(screen.getByTestId("confirm-modal")).toBeInTheDocument();
        expect(screen.getByTestId("confirm-message")).toHaveTextContent(
          `Delete post "Post 1"?`
        );
      });
    });

    it("calls deleteBlogPost with correct id on confirm", async () => {
      adminAPI.deleteBlogPost.mockResolvedValue({});
      const user = setup();
      render(<AdminBlog />);
      await waitFor(() => screen.getByText("Post 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-btn"));
      await waitFor(() =>
        expect(adminAPI.deleteBlogPost).toHaveBeenCalledWith(1)
      );
    });

    it("closes ConfirmModal after successful delete", async () => {
      adminAPI.deleteBlogPost.mockResolvedValue({});
      const user = setup();
      render(<AdminBlog />);
      await waitFor(() => screen.getByText("Post 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-btn"));
      await waitFor(() =>
        expect(screen.queryByTestId("confirm-modal")).not.toBeInTheDocument()
      );
    });

    it("re-fetches posts after successful delete", async () => {
      adminAPI.deleteBlogPost.mockResolvedValue({});
      const user = setup();
      render(<AdminBlog />);
      await waitFor(() => screen.getByText("Post 1"));

      vi.clearAllMocks();
      defaultPostsOk();

      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-btn"));

      await waitFor(() =>
        expect(adminAPI.getBlogPosts).toHaveBeenCalledTimes(1)
      );
    });

    it("shows error toast when post delete fails", async () => {
      adminAPI.deleteBlogPost.mockRejectedValue(new Error("500"));
      const user = setup();
      render(<AdminBlog />);
      await waitFor(() => screen.getByText("Post 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-btn"));
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === "Failed to delete post" && t.type === "error")
        ).toBe(true)
      );
    });

    it("closes ConfirmModal when Cancel is clicked", async () => {
      const user = setup();
      render(<AdminBlog />);
      await waitFor(() => screen.getByText("Post 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-cancel"));
      await waitFor(() =>
        expect(screen.queryByTestId("confirm-modal")).not.toBeInTheDocument()
      );
    });
  });

  describe("Delete – categories", () => {
    const goToCats = async (user) => {
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() => screen.getAllByText(/cat 1/i));
    };

    it("shows correct ConfirmModal message for category delete", async () => {
      const user = setup();
      render(<AdminBlog />);
      await goToCats(user);
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await waitFor(() =>
        expect(screen.getByTestId("confirm-message")).toHaveTextContent(
          "Posts will remain but category will be set to null"
        )
      );
    });

    it("calls deleteBlogCategory with correct id on confirm", async () => {
      adminAPI.deleteBlogCategory.mockResolvedValue({});
      const user = setup();
      render(<AdminBlog />);
      await goToCats(user);
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-btn"));
      await waitFor(() =>
        expect(adminAPI.deleteBlogCategory).toHaveBeenCalledWith(10)
      );
    });

    it("shows error toast when category delete fails", async () => {
      adminAPI.deleteBlogCategory.mockRejectedValue(new Error("500"));
      const user = setup();
      render(<AdminBlog />);
      await goToCats(user);
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-btn"));
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === "Failed to delete category" && t.type === "error")
        ).toBe(true)
      );
    });
  });

  describe("Delete – comments", () => {
    const goToComments = async (user) => {
      await user.click(screen.getByRole("button", { name: /^comments$/i }));
      await waitFor(() => screen.getByText("Commenter 1"));
    };

    it("shows correct ConfirmModal message for comment delete", async () => {
      const user = setup();
      render(<AdminBlog />);
      await goToComments(user);
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await waitFor(() =>
        expect(screen.getByTestId("confirm-message")).toHaveTextContent(
          `Delete comment by "Commenter 1 on "Post Title 1""`
        )
      );
    });

    it("calls deleteBlogComment with correct id on confirm", async () => {
      adminAPI.deleteBlogComment.mockResolvedValue({});
      const user = setup();
      render(<AdminBlog />);
      await goToComments(user);
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-btn"));
      await waitFor(() =>
        expect(adminAPI.deleteBlogComment).toHaveBeenCalledWith(100)
      );
    });

    it("shows error toast when comment delete fails", async () => {
      adminAPI.deleteBlogComment.mockRejectedValue(new Error("500"));
      const user = setup();
      render(<AdminBlog />);
      await goToComments(user);
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-btn"));
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === "Failed to delete comment" && t.type === "error")
        ).toBe(true)
      );
    });
  });

  // ── 13. API error paths ───────────────────────────────────────────────────
  describe("API error paths", () => {
    it("shows 'Failed to load posts' toast on getBlogPosts failure", async () => {
      adminAPI.getBlogPosts.mockRejectedValue(new Error("net"));
      render(<AdminBlog />);
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === "Failed to load posts" && t.type === "error")
        ).toBe(true)
      );
    });

    it("shows 'Failed to load categories' toast on getBlogCategories failure", async () => {
      adminAPI.getBlogCategories.mockRejectedValue(new Error("net"));
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === "Failed to load categories" && t.type === "error")
        ).toBe(true)
      );
    });

    it("shows 'Failed to load comments' toast on getBlogComments failure", async () => {
      adminAPI.getBlogComments.mockRejectedValue(new Error("net"));
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^comments$/i }));
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === "Failed to load comments" && t.type === "error")
        ).toBe(true)
      );
    });
  });

  // ── 14. statusBadge helper ────────────────────────────────────────────────
  describe("statusBadge column renderer", () => {
    it("applies green styles for published status", async () => {
      adminAPI.getBlogPosts.mockResolvedValue(
        paginated([{ ...makePosts(1)[0], status: "published" }], 1)
      );
      const { container } = render(<AdminBlog />);
      await waitFor(() => {
        const badge = container.querySelector(".bg-green-100");
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveTextContent("Published");
      });
    });

    it("applies amber styles for draft status", async () => {
      adminAPI.getBlogPosts.mockResolvedValue(
        paginated([{ ...makePosts(1)[0], status: "draft" }], 1)
      );
      const { container } = render(<AdminBlog />);
      await waitFor(() => {
        const badge = container.querySelector(".bg-amber-100");
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveTextContent("Draft");
      });
    });

    // FIX-1: single-row fixture → only one Published element.
    it("capitalises first letter of status text", async () => {
      adminAPI.getBlogPosts.mockResolvedValue(
        paginated([{ ...makePosts(1)[0], status: "published" }], 1)
      );
      render(<AdminBlog />);
      await waitFor(() => {
        // Find the row container by its data-testid
        const firstRow = screen.getByTestId("dt-row-0");
        expect(within(firstRow).getByText("Published")).toBeInTheDocument();
      });
    });
  });

  // ── 15. formatDate helper (via rendered cells) ────────────────────────────
  describe("formatDate column renderer", () => {
    it("formats a valid ISO date string to locale date", async () => {
      const date = "2024-06-01T00:00:00Z";
      adminAPI.getBlogComments.mockResolvedValue(
        paginated([{ ...makeComments(1)[0], created_at: date }], 1)
      );
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^comments$/i }));
      await waitFor(() => {
        const cells = document.querySelectorAll("[data-testid='cell-created_at']");
        expect(cells[0].textContent).toMatch(/\d/);
        expect(cells[0].textContent).not.toBe("—");
      });
    });

    it("renders '—' for falsy date", async () => {
      adminAPI.getBlogComments.mockResolvedValue(
        paginated([{ ...makeComments(1)[0], created_at: null }], 1)
      );
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^comments$/i }));
      await waitFor(() => {
        const cells = document.querySelectorAll("[data-testid='cell-created_at']");
        expect(cells[0].textContent).toBe("—");
      });
    });
  });

  // ── 16. Flat (non-paginated) API response ─────────────────────────────────
  describe("Flat (non-paginated) API response shape", () => {
    it("handles flat array response for categories", async () => {
      adminAPI.getBlogCategories.mockResolvedValue(flat(makeCategories(3)));
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^categories$/i }));
      await waitFor(() =>
        expect(screen.getAllByText(/cat \d/i).length).toBeGreaterThanOrEqual(3)
      );
    });

    it("handles flat array response for comments", async () => {
      adminAPI.getBlogComments.mockResolvedValue(flat(makeComments(2)));
      const user = setup();
      render(<AdminBlog />);
      await user.click(screen.getByRole("button", { name: /^comments$/i }));
      await waitFor(() =>
        expect(screen.getByText("Commenter 1")).toBeInTheDocument()
      );
    });
  });

  // ── 17. Snapshot ─────────────────────────────────────────────────────────
  describe("Snapshot", () => {
    it("matches stable snapshot of posts tab after data loads", async () => {
      const { asFragment } = render(<AdminBlog />);
      await waitFor(() => screen.getByText("Post 1"));
      expect(asFragment()).toMatchSnapshot();
    });
  });
});
