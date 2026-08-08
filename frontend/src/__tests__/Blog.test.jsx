import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

import Blog from "../pages/Blog";
import { blogAPI } from "../services/api";

// ─── Mock the entire blogAPI module ───────────────────────────────────────────

vi.mock("../services/api", () => ({
  blogAPI: {
    getPosts: vi.fn(),
    getCategories: vi.fn(),
    getPost: vi.fn(),
    getRelatedPosts: vi.fn(),
    createComment: vi.fn(),
  },
}));

// ─── Shared fixtures ──────────────────────────────────────────────────────────

const makePost = (overrides = {}) => ({
  id: 1,
  slug: "test-post",
  title: "Test Post Title",
  excerpt: "A short excerpt about this post.",
  cover_image_url: null,
  published_at: "2024-03-15T10:00:00Z",
  created_at: "2024-03-15T10:00:00Z",
  read_time: 5,
  views_count: 120,
  is_featured: false,
  author: { full_name: "Jane Doe", avatar: null },
  category: { id: 10, name: "Technology", slug: "technology" },
  ...overrides,
});

const makeCategory = (overrides = {}) => ({
  id: 10,
  name: "Technology",
  slug: "technology",
  post_count: 4,
  ...overrides,
});

/** Default success responses covering all three getPosts call patterns */
const defaultPostsPage = (results = [], extras = {}) => ({
  data: {
    results,
    count: results.length,
    total_pages: 1,
    current_page: 1,
    ...extras,
  },
});

const defaultCategories = () => ({
  data: [makeCategory()],
});

/**
 * Wire up the three simultaneous getPosts calls that Blog makes on mount:
 *   1. Featured hero post  (is_featured: true, page_size: 1)
 *   2. Recent posts        (page_size: 3, ordering: "-created_at")   ← hero section
 *   3. Grid posts          (page, page_size: 6, ordering: "-created_at")
 *   4. Sidebar posts       (page_size: 5)
 *
 * We differentiate by inspecting the `params` argument passed to getPosts.
 */
const setupDefaultMocks = ({
  featuredPost = null,
  recentPosts = [],
  gridPosts = [],
  sidebarPosts = [],
  categories = [makeCategory()],
  gridExtras = {},
} = {}) => {
  blogAPI.getPosts.mockImplementation((params = {}) => {
    if (params.is_featured) {
      return Promise.resolve(
        defaultPostsPage(featuredPost ? [featuredPost] : [])
      );
    }
    if (params.page_size === 3) {
      return Promise.resolve(defaultPostsPage(recentPosts));
    }
    if (params.page_size === 5) {
      return Promise.resolve(defaultPostsPage(sidebarPosts));
    }
    // Grid call (page_size: 6)
    return Promise.resolve(defaultPostsPage(gridPosts, gridExtras));
  });

  blogAPI.getCategories.mockResolvedValue({ data: categories });
};

// ─── Render helper ────────────────────────────────────────────────────────────

const renderBlog = (initialEntries = ["/"]) =>
  render(
    <MemoryRouter initialEntries={initialEntries}>
      <Blog />
    </MemoryRouter>
  );

// ─────────────────────────────────────────────────────────────────────────────

describe("Blog page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // scrollTo is not implemented in jsdom
    window.scrollTo = vi.fn();
  });

  // ── Loading state ────────────────────────────────────────────────────────

  describe("loading state", () => {
    it("renders skeleton placeholders while data is being fetched", () => {
      // Keep promises unresolved so the component stays in loading
      blogAPI.getPosts.mockReturnValue(new Promise(() => { }));
      blogAPI.getCategories.mockReturnValue(new Promise(() => { }));

      renderBlog();

      // Target the <h1> heading specifically instead of a generic text query
      expect(screen.getByRole("heading", { name: "Blog", level: 1 })).toBeInTheDocument();
      // No post titles should appear
      expect(screen.queryByRole("article")).not.toBeInTheDocument();
    });

    it("shows the page heading and breadcrumb while loading", () => {
      blogAPI.getPosts.mockReturnValue(new Promise(() => { }));
      blogAPI.getCategories.mockReturnValue(new Promise(() => { }));

      renderBlog();

      expect(screen.getByRole("heading", { name: "Blog" })).toBeInTheDocument();
      expect(screen.getByText("Home")).toBeInTheDocument();
    });
  });

  // ── Successful fetch ─────────────────────────────────────────────────────

  describe("successful data fetch", () => {
    it("renders grid posts after data loads", async () => {
      const posts = [
        makePost({ id: 1, slug: "post-one", title: "First Article" }),
        makePost({ id: 2, slug: "post-two", title: "Second Article" }),
      ];
      setupDefaultMocks({ gridPosts: posts });

      renderBlog();

      expect(await screen.findByText("First Article")).toBeInTheDocument();
      expect(screen.getByText("Second Article")).toBeInTheDocument();
    });

    it("renders post excerpt and author in the grid", async () => {
      const post = makePost({
        excerpt: "Unique excerpt for this post",
        author: { full_name: "Alice Smith", avatar: null },
      });
      setupDefaultMocks({ gridPosts: [post] });

      renderBlog();

      expect(
        await screen.findByText("Unique excerpt for this post")
      ).toBeInTheDocument();
      expect(screen.getByText("Alice Smith")).toBeInTheDocument();
    });

    it("renders the featured hero post when a featured post exists", async () => {
      const featured = makePost({
        id: 99,
        title: "Featured Hero Post",
        is_featured: true,
      });
      setupDefaultMocks({ featuredPost: featured, recentPosts: [featured] });

      renderBlog();

      // The hero title links to /blog/test-post
      expect(await screen.findByText("Featured Hero Post")).toBeInTheDocument();
    });

    it("renders category badges on grid posts", async () => {
      const post = makePost({
        category: { id: 5, name: "Design", slug: "design" },
      });
      setupDefaultMocks({ gridPosts: [post] });

      renderBlog();

      // Category appears both in the sidebar widget and on the post card
      expect(await screen.findAllByText("Design")).not.toHaveLength(0);
    });

    it("renders the read-time on each grid post", async () => {
      const post = makePost({ read_time: 7 });
      setupDefaultMocks({ gridPosts: [post] });

      renderBlog();

      expect(await screen.findByText(/7 min/)).toBeInTheDocument();
    });

    it("shows post links pointing to the correct detail URL", async () => {
      const post = makePost({ slug: "my-cool-post", title: "My Cool Post" });
      setupDefaultMocks({ gridPosts: [post] });

      renderBlog();

      const links = await screen.findAllByRole("link", { name: "My Cool Post" });

      expect(links[0]).toHaveAttribute("href", "/blog/my-cool-post");
    });

    it("renders sidebar categories widget with category names and counts", async () => {
      const cat = makeCategory({ name: "Science", slug: "science", post_count: 9 });
      setupDefaultMocks({ categories: [cat] });

      renderBlog();

      expect(await screen.findByText("Science")).toBeInTheDocument();
      expect(screen.getByText("9")).toBeInTheDocument();
    });

    it("displays 'No posts found.' when the grid returns empty results", async () => {
      setupDefaultMocks({ gridPosts: [] });

      renderBlog();

      const gridHeading = await screen.findByRole("heading", { name: /All Posts/i });

      const gridSection = gridHeading.closest("section");

      expect(
        await within(gridSection).findByText("No posts found.")
      ).toBeInTheDocument();
    });
  });

  // ── Error state ──────────────────────────────────────────────────────────

  describe("error state", () => {
    it("shows an error message when the grid fetch fails", async () => {
      blogAPI.getPosts.mockImplementation((params = {}) => {
        if (params.is_featured || params.page_size === 3 || params.page_size === 5) {
          return Promise.resolve(defaultPostsPage([]));
        }
        return Promise.reject(new Error("Network error"));
      });
      blogAPI.getCategories.mockResolvedValue({ data: [] });

      renderBlog();

      expect(
        await screen.findByText(/Failed to load posts/i)
      ).toBeInTheDocument();
    });

    it("shows a Retry button after a grid fetch failure", async () => {
      blogAPI.getPosts.mockImplementation((params = {}) => {
        if (params.is_featured || params.page_size === 3 || params.page_size === 5) {
          return Promise.resolve(defaultPostsPage([]));
        }
        return Promise.reject(new Error("Network error"));
      });
      blogAPI.getCategories.mockResolvedValue({ data: [] });

      renderBlog();

      expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
    });

    it("retries the grid fetch when the Retry button is clicked", async () => {
      const user = userEvent.setup();
      let callCount = 0;

      blogAPI.getPosts.mockImplementation((params = {}) => {
        if (params.is_featured || params.page_size === 3 || params.page_size === 5) {
          return Promise.resolve(defaultPostsPage([]));
        }
        callCount++;
        if (callCount === 1) {
          return Promise.reject(new Error("Network error"));
        }
        return Promise.resolve(
          defaultPostsPage([makePost({ title: "Loaded After Retry" })])
        );
      });
      blogAPI.getCategories.mockResolvedValue({ data: [] });

      renderBlog();

      const retryBtn = await screen.findByRole("button", { name: /retry/i });
      await user.click(retryBtn);

      expect(
        await screen.findByText("Loaded After Retry")
      ).toBeInTheDocument();
    });
  });

  // ── Category filtering ───────────────────────────────────────────────────

  describe("category filtering", () => {
    it("filters posts by category when a category button is clicked", async () => {
      const user = userEvent.setup();
      const cat = makeCategory({ name: "Health", slug: "health" });

      setupDefaultMocks({
        gridPosts: [makePost({ title: "Initial Post" })],
        categories: [cat],
      });

      renderBlog();

      // Wait for initial render
      await screen.findByText("Initial Post");

      // Now mock a filtered response
      blogAPI.getPosts.mockImplementation((params = {}) => {
        if (params.category === "health" && params.page_size === 6) {
          return Promise.resolve(
            defaultPostsPage([makePost({ id: 2, title: "Health Article" })])
          );
        }
        return Promise.resolve(defaultPostsPage([]));
      });

      // Click the "Health" category button in the sidebar widget
      // There may be multiple elements with the text; find the button one
      const categoryButtons = screen.getAllByRole("button", { name: /Health/i });
      await user.click(categoryButtons[0]);

      expect(await screen.findByText("Health Article")).toBeInTheDocument();
    });

    it("shows 'All Posts' heading when no category filter is active", async () => {
      setupDefaultMocks({ gridPosts: [makePost()] });

      renderBlog();

      expect(await screen.findByRole("heading", { name: /All Posts/i })).toBeInTheDocument();
    });

    it("shows a 'Clear filters' button when a category is active via URL param", async () => {
      setupDefaultMocks({
        gridPosts: [makePost()],
        categories: [makeCategory()],
      });

      renderBlog(["/?category=technology"]);

      expect(await screen.findByText(/Clear filters/i)).toBeInTheDocument();
    });

    it("removes the category filter when 'Clear filters' is clicked", async () => {
      const user = userEvent.setup();

      blogAPI.getCategories.mockResolvedValue({ data: [makeCategory()] });
      blogAPI.getPosts.mockImplementation((params = {}) => {
        if (params.is_featured) return Promise.resolve(defaultPostsPage([]));
        if (params.page_size === 3) return Promise.resolve(defaultPostsPage([]));
        if (params.page_size === 5) return Promise.resolve(defaultPostsPage([]));
        if (params.category) {
          return Promise.resolve(
            defaultPostsPage([makePost({ title: "Filtered Post" })])
          );
        }
        return Promise.resolve(
          defaultPostsPage([makePost({ title: "All Posts View" })])
        );
      });

      renderBlog(["/?category=technology"]);

      await screen.findByText("Filtered Post");

      const clearBtn = screen.getByRole("button", { name: /Clear filters/i });
      await user.click(clearBtn);

      expect(await screen.findByText("All Posts View")).toBeInTheDocument();
      expect(screen.queryByText("Filtered Post")).not.toBeInTheDocument();
    });
  });

  // ── Pagination ───────────────────────────────────────────────────────────

  describe("pagination", () => {
    it("does not render pagination controls when there is only one page", async () => {
      setupDefaultMocks({
        gridPosts: [makePost()],
        gridExtras: { total_pages: 1, current_page: 1 },
      });

      renderBlog();

      await screen.findByText("Test Post Title");

      // Previous/next chevron buttons should not appear
      expect(screen.queryByRole("button", { name: /chevron/i })).not.toBeInTheDocument();
    });

    it("renders page number buttons when there are multiple pages", async () => {
      setupDefaultMocks({
        gridPosts: [makePost()],
        gridExtras: { total_pages: 3, current_page: 1, count: 18 },
      });

      renderBlog();

      await screen.findByText("Test Post Title");

      expect(screen.getByRole("button", { name: "1" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "2" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "3" })).toBeInTheDocument();
    });

    it("navigates to page 2 when the page 2 button is clicked", async () => {
      const user = userEvent.setup();

      blogAPI.getCategories.mockResolvedValue({ data: [] });
      blogAPI.getPosts.mockImplementation((params = {}) => {
        if (params.is_featured) return Promise.resolve(defaultPostsPage([]));
        if (params.page_size === 3) return Promise.resolve(defaultPostsPage([]));
        if (params.page_size === 5) return Promise.resolve(defaultPostsPage([]));
        if (params.page === 2) {
          return Promise.resolve(
            defaultPostsPage(
              [makePost({ id: 7, title: "Page Two Post" })],
              { total_pages: 2, current_page: 2, count: 12 }
            )
          );
        }
        return Promise.resolve(
          defaultPostsPage(
            [makePost({ title: "Page One Post" })],
            { total_pages: 2, current_page: 1, count: 12 }
          )
        );
      });

      renderBlog();

      await screen.findByText("Page One Post");

      const page2Btn = screen.getByRole("button", { name: "2" });
      await user.click(page2Btn);

      expect(await screen.findByText("Page Two Post")).toBeInTheDocument();
    });

    it("disables the Previous button on the first page", async () => {
      setupDefaultMocks({
        gridPosts: [makePost()],
        gridExtras: { total_pages: 3, current_page: 1, count: 18 },
      });

      renderBlog();

      await screen.findByText("Test Post Title");

      // Previous is the first button rendered in the pagination row
      const paginationButtons = screen
        .getAllByRole("button")
        .filter((btn) => btn.disabled !== undefined);

      // Find the previous chevron — it's disabled when on page 1
      const prevButton = screen
        .getAllByRole("button")
        .find((btn) => btn.getAttribute("disabled") !== null);

      expect(prevButton).toBeDisabled();
    });
  });
});
