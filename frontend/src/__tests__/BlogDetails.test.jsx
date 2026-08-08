import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

import BlogDetails from "../pages/BlogDetails";
import { blogAPI, parseErrors } from "../services/api";

// ─── Mock the entire blogAPI module ───────────────────────────────────────────

vi.mock("../services/api", () => ({
  blogAPI: {
    getPosts: vi.fn(),
    getCategories: vi.fn(),
    getPost: vi.fn(),
    getRelatedPosts: vi.fn(),
    createComment: vi.fn(),
  },
  parseErrors: vi.fn(),
}));

// ─── Shared fixtures ──────────────────────────────────────────────────────────

const makePost = (overrides = {}) => ({
  id: 1,
  slug: "my-test-post",
  title: "My Test Post",
  excerpt: "An excerpt for the test post.",
  content: "<p>Body content of the post.</p>",
  cover_image_url: null,
  published_at: "2024-03-15T10:00:00Z",
  created_at: "2024-03-15T10:00:00Z",
  read_time: 6,
  views_count: 250,
  author: { full_name: "John Author", avatar: null },
  category: { id: 10, name: "Technology", slug: "technology" },
  comments: [],
  ...overrides,
});

const makeComment = (overrides = {}) => ({
  id: 100,
  name: "Commenter One",
  email: "commenter@example.com",
  body: "This is a comment body.",
  created_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(), // 1 hour ago
  author_avatar: null,
  replies: [],
  ...overrides,
});

const makeRelatedPost = (overrides = {}) => ({
  id: 20,
  slug: "related-post",
  title: "Related Post Title",
  cover_image_url: null,
  published_at: "2024-02-10T08:00:00Z",
  created_at: "2024-02-10T08:00:00Z",
  category: { id: 10, name: "Technology", slug: "technology" },
  ...overrides,
});

// ─── Render helper ────────────────────────────────────────────────────────────

/**
 * Renders BlogDetails inside a MemoryRouter with a proper matched route so that
 * useParams() receives the correct `slug` value.
 */
const renderBlogDetails = (slug = "my-test-post") =>
  render(
    <MemoryRouter initialEntries={[`/blog/${slug}`]}>
      <Routes>
        <Route path="/blog/:slug" element={<BlogDetails />} />
        <Route path="/blog" element={<div>Blog List</div>} />
      </Routes>
    </MemoryRouter>
  );

// ─────────────────────────────────────────────────────────────────────────────

describe("BlogDetails page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.scrollTo = vi.fn();
  });

  // ── Loading state ────────────────────────────────────────────────────────

  describe("loading state", () => {
    it("renders a skeleton while the post is being fetched", () => {
      blogAPI.getPost.mockReturnValue(new Promise(() => { }));
      blogAPI.getRelatedPosts.mockReturnValue(new Promise(() => { }));

      renderBlogDetails();

      // No post title or content yet
      expect(screen.queryByRole("heading", { name: "My Test Post" })).not.toBeInTheDocument();
      // The loading skeleton is rendered — the leave-comment heading doesn't appear yet
      expect(screen.queryByText("Leave a Comment")).not.toBeInTheDocument();
    });

    it("does not render the comment form during loading", () => {
      blogAPI.getPost.mockReturnValue(new Promise(() => { }));
      blogAPI.getRelatedPosts.mockReturnValue(new Promise(() => { }));

      renderBlogDetails();

      expect(screen.queryByRole("button", { name: /Post Comment/i })).not.toBeInTheDocument();
    });
  });

  // ── Successful post rendering ────────────────────────────────────────────

  describe("successful post rendering", () => {
    beforeEach(() => {
      blogAPI.getPost.mockResolvedValue({ data: makePost() });
      blogAPI.getRelatedPosts.mockResolvedValue({ data: [] });
    });

    it("renders the post title as a heading", async () => {
      renderBlogDetails();

      expect(
        await screen.findByRole("heading", { name: "My Test Post" })
      ).toBeInTheDocument();
    });

    it("renders the post read time", async () => {
      renderBlogDetails();

      expect(await screen.findByText(/6 min read/i)).toBeInTheDocument();
    });

    it("renders the post view count", async () => {
      renderBlogDetails();

      expect(await screen.findByText(/250/)).toBeInTheDocument();
    });

    it("renders the category badge linking to the filtered blog list", async () => {
      renderBlogDetails();

      const categoryLink = await screen.findByRole("link", { name: "Technology" });
      expect(categoryLink).toHaveAttribute("href", "/blog?category=technology");
    });

    it("renders the post HTML content via dangerouslySetInnerHTML", async () => {
      renderBlogDetails();

      // The content '<p>Body content of the post.</p>' should appear in the DOM
      expect(await screen.findByText("Body content of the post.")).toBeInTheDocument();
    });

    it("renders the comment form with all required fields", async () => {
      renderBlogDetails();

      await screen.findByText("Leave a Comment");

      expect(screen.getByPlaceholderText(/Enter your full name/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/Enter your email address/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/Write your thoughts here/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Post Comment/i })).toBeInTheDocument();
    });

    it("renders breadcrumb navigation with links to Home and Blog", async () => {
      renderBlogDetails();

      await screen.findByRole("heading", { name: "My Test Post" });

      expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
      expect(screen.getByRole("link", { name: "Blog" })).toHaveAttribute("href", "/blog");
    });
  });

  // ── 404 / not-found state ────────────────────────────────────────────────

  describe("404 state", () => {
    it("renders a 'Post not found' message when the API returns 404", async () => {
      const notFoundError = { response: { status: 404 } };
      blogAPI.getPost.mockRejectedValue(notFoundError);
      blogAPI.getRelatedPosts.mockResolvedValue({ data: [] });

      renderBlogDetails("non-existent-slug");

      expect(await screen.findByText("Post not found")).toBeInTheDocument();
      expect(
        screen.getByText(/This post may have been removed/i)
      ).toBeInTheDocument();
    });

    it("renders a 'Back to Blog' link on the 404 screen", async () => {
      blogAPI.getPost.mockRejectedValue({ response: { status: 404 } });
      blogAPI.getRelatedPosts.mockResolvedValue({ data: [] });

      renderBlogDetails("ghost-slug");

      const backLink = await screen.findByRole("link", { name: /Back to Blog/i });
      expect(backLink).toHaveAttribute("href", "/blog");
    });

    it("does not render the comment form on the 404 screen", async () => {
      blogAPI.getPost.mockRejectedValue({ response: { status: 404 } });
      blogAPI.getRelatedPosts.mockResolvedValue({ data: [] });

      renderBlogDetails("ghost-slug");

      await screen.findByText("Post not found");
      expect(screen.queryByText("Leave a Comment")).not.toBeInTheDocument();
    });
  });

  // ── Comments list ────────────────────────────────────────────────────────

  describe("rendering comments", () => {
    it("renders the comments section when the post has comments", async () => {
      const comments = [
        makeComment({ id: 1, name: "Alice", body: "Great article!" }),
        makeComment({ id: 2, name: "Bob", body: "Very informative." }),
      ];
      blogAPI.getPost.mockResolvedValue({ data: makePost({ comments }) });
      blogAPI.getRelatedPosts.mockResolvedValue({ data: [] });

      renderBlogDetails();

      expect(await screen.findByText("Alice")).toBeInTheDocument();
      expect(screen.getByText("Great article!")).toBeInTheDocument();
      expect(screen.getByText("Bob")).toBeInTheDocument();
      expect(screen.getByText("Very informative.")).toBeInTheDocument();
    });

    it("shows the correct comment count in the section heading", async () => {
      const comments = [makeComment({ id: 1 }), makeComment({ id: 2 }), makeComment({ id: 3 })];
      blogAPI.getPost.mockResolvedValue({ data: makePost({ comments }) });
      blogAPI.getRelatedPosts.mockResolvedValue({ data: [] });

      renderBlogDetails();

      // The heading reads "3 Comments"
      expect(await screen.findByRole("heading", { name: /3 Comments/i })).toBeInTheDocument();
    });

    it("does not render the comments section when there are no comments", async () => {
      blogAPI.getPost.mockResolvedValue({ data: makePost({ comments: [] }) });
      blogAPI.getRelatedPosts.mockResolvedValue({ data: [] });

      renderBlogDetails();

      await screen.findByText("Leave a Comment");

      expect(screen.queryByRole("heading", { name: /Comments/i })).not.toBeInTheDocument();
    });

    it("renders comment replies nested under the parent comment", async () => {
      const reply = {
        id: 201,
        name: "Reply Author",
        body: "Thanks for sharing!",
        created_at: new Date().toISOString(),
      };
      const comment = makeComment({
        id: 200,
        name: "Parent Author",
        body: "Original comment.",
        replies: [reply],
      });
      blogAPI.getPost.mockResolvedValue({ data: makePost({ comments: [comment] }) });
      blogAPI.getRelatedPosts.mockResolvedValue({ data: [] });

      renderBlogDetails();

      expect(await screen.findByText("Original comment.")).toBeInTheDocument();
      expect(screen.getByText("Thanks for sharing!")).toBeInTheDocument();
      expect(screen.getByText("Reply Author")).toBeInTheDocument();
    });
  });

  // ── Related posts ────────────────────────────────────────────────────────

  describe("related posts", () => {
    it("renders the related posts section when related posts are returned", async () => {
      const related = [
        makeRelatedPost({ id: 21, slug: "related-one", title: "Related One" }),
        makeRelatedPost({ id: 22, slug: "related-two", title: "Related Two" }),
      ];
      blogAPI.getPost.mockResolvedValue({ data: makePost() });
      blogAPI.getRelatedPosts.mockResolvedValue({ data: related });

      renderBlogDetails();

      expect(await screen.findByRole("heading", { name: "Related Posts" })).toBeInTheDocument();
      expect(screen.getByText("Related One")).toBeInTheDocument();
      expect(screen.getByText("Related Two")).toBeInTheDocument();
    });

    it("does not render the related posts section when the list is empty", async () => {
      blogAPI.getPost.mockResolvedValue({ data: makePost() });
      blogAPI.getRelatedPosts.mockResolvedValue({ data: [] });

      renderBlogDetails();

      await screen.findByText("Leave a Comment");

      expect(
        screen.queryByRole("heading", { name: "Related Posts" })
      ).not.toBeInTheDocument();
    });

    it("also handles related posts returned under a results key", async () => {
      const related = [makeRelatedPost({ id: 30, title: "Via Results Key" })];
      blogAPI.getPost.mockResolvedValue({ data: makePost() });
      blogAPI.getRelatedPosts.mockResolvedValue({ data: { results: related } });

      renderBlogDetails();

      expect(await screen.findByText("Via Results Key")).toBeInTheDocument();
    });
  });

  // ── Comment form — success ───────────────────────────────────────────────

  describe("comment form — successful submission", () => {
    beforeEach(() => {
      blogAPI.getPost.mockResolvedValue({ data: makePost() });
      blogAPI.getRelatedPosts.mockResolvedValue({ data: [] });
    });

    it("submits the comment form and shows a success message", async () => {
      const user = userEvent.setup();
      const newComment = makeComment({
        id: 999,
        name: "New Commenter",
        body: "A brand new comment.",
      });
      blogAPI.createComment.mockResolvedValue({ data: newComment });

      renderBlogDetails();

      await screen.findByText("Leave a Comment");

      await user.type(
        screen.getByPlaceholderText(/Enter your full name/i),
        "New Commenter"
      );
      await user.type(
        screen.getByPlaceholderText(/Enter your email address/i),
        "new@example.com"
      );
      await user.type(
        screen.getByPlaceholderText(/Write your thoughts here/i),
        "A brand new comment."
      );

      await user.click(screen.getByRole("button", { name: /Post Comment/i }));

      expect(
        await screen.findByText(/Your comment has been posted successfully/i)
      ).toBeInTheDocument();
    });

    it("calls createComment with the correct slug and payload", async () => {
      const user = userEvent.setup();
      blogAPI.createComment.mockResolvedValue({ data: makeComment() });

      renderBlogDetails("my-test-post");

      await screen.findByText("Leave a Comment");

      await user.type(screen.getByPlaceholderText(/Enter your full name/i), "Test User");
      await user.type(screen.getByPlaceholderText(/Enter your email address/i), "test@test.com");
      await user.type(screen.getByPlaceholderText(/Write your thoughts here/i), "My comment text.");

      await user.click(screen.getByRole("button", { name: /Post Comment/i }));

      await waitFor(() => {
        expect(blogAPI.createComment).toHaveBeenCalledWith("my-test-post", {
          name: "Test User",
          email: "test@test.com",
          body: "My comment text.",
        });
      });
    });

    it("appends the new comment to the comments list after a successful submission", async () => {
      const user = userEvent.setup();
      const newComment = makeComment({
        id: 555,
        name: "Appended Author",
        body: "Appended comment body.",
      });
      blogAPI.createComment.mockResolvedValue({ data: newComment });

      renderBlogDetails();

      await screen.findByText("Leave a Comment");

      await user.type(screen.getByPlaceholderText(/Enter your full name/i), "Appended Author");
      await user.type(screen.getByPlaceholderText(/Enter your email address/i), "a@b.com");
      await user.type(screen.getByPlaceholderText(/Write your thoughts here/i), "Appended comment body.");

      await user.click(screen.getByRole("button", { name: /Post Comment/i }));

      expect(await screen.findByText("Appended comment body.")).toBeInTheDocument();
    });

    it("clears the form fields after a successful submission", async () => {
      const user = userEvent.setup();
      blogAPI.createComment.mockResolvedValue({ data: makeComment() });

      renderBlogDetails();

      await screen.findByText("Leave a Comment");

      const nameInput = screen.getByPlaceholderText(/Enter your full name/i);
      const emailInput = screen.getByPlaceholderText(/Enter your email address/i);
      const bodyTextarea = screen.getByPlaceholderText(/Write your thoughts here/i);

      await user.type(nameInput, "Someone");
      await user.type(emailInput, "someone@mail.com");
      await user.type(bodyTextarea, "Some comment.");

      await user.click(screen.getByRole("button", { name: /Post Comment/i }));

      await waitFor(() => {
        expect(nameInput).toHaveValue("");
        expect(emailInput).toHaveValue("");
        expect(bodyTextarea).toHaveValue("");
      });
    });

    it("includes the optional website field in the payload when provided", async () => {
      const user = userEvent.setup();
      blogAPI.createComment.mockResolvedValue({ data: makeComment() });

      renderBlogDetails();

      await screen.findByText("Leave a Comment");

      await user.type(screen.getByPlaceholderText(/Enter your full name/i), "Webmaster");
      await user.type(screen.getByPlaceholderText(/Enter your email address/i), "web@site.com");
      await user.type(screen.getByPlaceholderText(/https:\/\/your-website/i), "https://mysite.com");
      await user.type(screen.getByPlaceholderText(/Write your thoughts here/i), "Cool post!");

      await user.click(screen.getByRole("button", { name: /Post Comment/i }));

      await waitFor(() => {
        expect(blogAPI.createComment).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({ website: "https://mysite.com" })
        );
      });
    });
  });

  // ── Comment form — validation errors ────────────────────────────────────

  describe("comment form — validation errors", () => {
    beforeEach(() => {
      blogAPI.getPost.mockResolvedValue({ data: makePost() });
      blogAPI.getRelatedPosts.mockResolvedValue({ data: [] });
    });

    it("displays field-level validation errors returned from the API", async () => {
      const user = userEvent.setup();
      const apiError = {
        response: {
          status: 400,
          data: {
            name: ["This field is required."],
            body: ["Comment must be at least 10 characters."],
          },
        },
      };
      blogAPI.createComment.mockRejectedValue(apiError);
      parseErrors.mockReturnValue({
        name: "This field is required.",
        body: "Comment must be at least 10 characters.",
      });

      renderBlogDetails();

      await screen.findByText("Leave a Comment");

      // Submit with minimal input to trigger server-side errors
      await user.click(screen.getByRole("button", { name: /Post Comment/i }));

      expect(await screen.findByText("This field is required.")).toBeInTheDocument();
      expect(
        screen.getByText("Comment must be at least 10 characters.")
      ).toBeInTheDocument();
    });

    it("displays a non-field error banner when a global API error occurs", async () => {
      const user = userEvent.setup();
      blogAPI.createComment.mockRejectedValue(new Error("Network error"));
      parseErrors.mockReturnValue({
        non_field_errors: "Network error. Please try again.",
      });

      renderBlogDetails();

      await screen.findByText("Leave a Comment");

      await user.click(screen.getByRole("button", { name: /Post Comment/i }));

      expect(
        await screen.findByText("Network error. Please try again.")
      ).toBeInTheDocument();
    });

    it("clears a field error when the user starts typing in that field", async () => {
      const user = userEvent.setup();
      blogAPI.createComment.mockRejectedValue({ response: { status: 400, data: {} } });
      parseErrors.mockReturnValue({ name: "Name is required." });

      renderBlogDetails();

      await screen.findByText("Leave a Comment");

      await user.click(screen.getByRole("button", { name: /Post Comment/i }));
      await screen.findByText("Name is required.");

      // Now type in the name field — the error should be cleared
      await user.type(screen.getByPlaceholderText(/Enter your full name/i), "A");

      expect(screen.queryByText("Name is required.")).not.toBeInTheDocument();
    });

    it("disables the submit button and shows a spinner while the request is in flight", async () => {
      const user = userEvent.setup();

      let resolveComment;
      blogAPI.createComment.mockReturnValue(
        new Promise((resolve) => { resolveComment = resolve; })
      );

      renderBlogDetails();

      await screen.findByText("Leave a Comment");

      await user.type(screen.getByPlaceholderText(/Enter your full name/i), "Someone");
      await user.type(screen.getByPlaceholderText(/Enter your email address/i), "s@s.com");
      await user.type(screen.getByPlaceholderText(/Write your thoughts here/i), "A comment.");

      await user.click(screen.getByRole("button", { name: /Post Comment/i }));

      // While still in-flight the button should be disabled and show "Posting…"
      await waitFor(() => {
        const btn = screen.getByRole("button", { name: /Posting/i });
        expect(btn).toBeDisabled();
      });

      // Resolve to clean up
      resolveComment({ data: makeComment() });
    });
  });
});
