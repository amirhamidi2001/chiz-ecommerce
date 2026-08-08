import { useEffect, useState, useRef } from "react";
import { adminAPI } from "../../services/api";
import DataTable from "../../components/admin/DataTable";
import ConfirmModal from "../../components/admin/ConfirmModal";
import Toast, { useToast } from "../../components/admin/Toast";

const statusBadge = (status) => {
  const styles = {
    draft: "bg-amber-100 text-amber-700",
    published: "bg-green-100 text-green-700",
  };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${styles[status] || "bg-gray-100"}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};

const formatDate = (iso) => iso ? new Date(iso).toLocaleDateString() : "—";

// ── Modal for Blog Post ─────────────────────────────────────────────────────
const PostModal = ({ post, categories, onClose, onSaved }) => {
  const [form, setForm] = useState({
    title: post?.title || "",
    excerpt: post?.excerpt || "",
    content: post?.content || "",
    category: post?.category || "",
    status: post?.status || "draft",
    is_featured: post?.is_featured ?? false,
  });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [coverPreview, setCoverPreview] = useState(post?.cover_image_url || null);
  const coverRef = useRef(null);
  const [coverFile, setCoverFile] = useState(null);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((p) => ({ ...p, [name]: type === "checkbox" ? checked : value }));
    setErrors((p) => ({ ...p, [name]: undefined }));
  };

  const handleCover = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    setCoverFile(f);
    setCoverPreview(URL.createObjectURL(f));
  };

  const validate = () => {
    const e = {};
    if (!form.title.trim()) e.title = "Title is required";
    if (!form.category) e.category = "Category is required";
    if (!form.content.trim()) e.content = "Content is required";
    return e;
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    const e = validate();
    if (Object.keys(e).length) {
      setErrors(e);
      return;
    }
    setSaving(true);
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => fd.append(k, v));
      if (coverFile) fd.append("cover_image", coverFile);
      if (post) {
        await adminAPI.updateBlogPost(post.id, fd);
      } else {
        await adminAPI.createBlogPost(fd);
      }
      onSaved();
      onClose();
    } catch (err) {
      setErrors(err?.response?.data || {});
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center p-6 border-b sticky top-0 bg-white z-10">
          <h3 className="text-lg font-bold">{post ? "Edit Post" : "New Blog Post"}</h3>
          <button onClick={onClose}><i className="bi bi-x-lg text-xl text-gray-400 hover:text-gray-600"></i></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Title *</label>
            <input name="title" value={form.title} onChange={handleChange}
              className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500 ${errors.title ? "border-red-400" : "border-gray-200"}`} />
            {errors.title && <p className="text-red-500 text-xs mt-0.5">{errors.title}</p>}
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Category *</label>
            <select name="category" value={form.category} onChange={handleChange}
              className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500 ${errors.category ? "border-red-400" : "border-gray-200"}`}>
              <option value="">Select category</option>
              {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            {errors.category && <p className="text-red-500 text-xs mt-0.5">{errors.category}</p>}
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Status</label>
              <select name="status" value={form.status} onChange={handleChange}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                <option value="draft">Draft</option>
                <option value="published">Published</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Featured</label>
              <div className="flex items-center h-10">
                <input type="checkbox" name="is_featured" checked={form.is_featured} onChange={handleChange}
                  className="w-4 h-4 accent-teal-600 mr-2" />
                <span className="text-sm text-gray-700">Mark as featured</span>
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Excerpt (short description)</label>
            <textarea name="excerpt" value={form.excerpt} onChange={handleChange} rows={2}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500 resize-none" />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Content *</label>
            <textarea name="content" value={form.content} onChange={handleChange} rows={8}
              className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none font-mono ${errors.content ? "border-red-400" : "border-gray-200"}`} />
            {errors.content && <p className="text-red-500 text-xs mt-0.5">{errors.content}</p>}
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-2">Cover Image</label>
            <div className="flex items-center gap-4">
              {coverPreview && (
                <img src={coverPreview} alt="" className="w-20 h-20 object-cover rounded-xl border" />
              )}
              <button type="button" onClick={() => coverRef.current?.click()}
                className="px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50 transition">
                <i className="bi bi-upload mr-1.5"></i> Upload
              </button>
              <input ref={coverRef} type="file" accept="image/*" className="hidden" onChange={handleCover} />
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 py-2.5 border border-gray-200 text-gray-700 rounded-xl text-sm hover:bg-gray-50 transition">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 py-2.5 bg-teal-600 text-white rounded-xl text-sm font-semibold hover:bg-teal-700 transition disabled:opacity-60">
              {saving ? "Saving…" : post ? "Update Post" : "Create Post"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ── Category modal (simple) ──────────────────────────────────────────────────
const CategoryModal = ({ category, onClose, onSaved }) => {
  const [name, setName] = useState(category?.name || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setSaving(true);
    try {
      const fd = new FormData();
      fd.append("name", name);
      if (category) {
        await adminAPI.updateBlogCategory(category.id, fd);
      } else {
        await adminAPI.createBlogCategory(fd);
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err?.response?.data?.name?.[0] || "Failed to save category");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center p-6 border-b">
          <h3 className="text-lg font-bold">{category ? "Edit Category" : "New Category"}</h3>
          <button onClick={onClose}><i className="bi bi-x-lg text-xl text-gray-400"></i></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6">
          <label className="block text-xs font-semibold text-gray-600 mb-1">Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} autoFocus
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500" />
          {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
          <div className="flex gap-3 mt-6">
            <button type="button" onClick={onClose}
              className="flex-1 py-2 border border-gray-200 rounded-xl text-sm hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={saving}
              className="flex-1 py-2 bg-teal-600 text-white rounded-xl text-sm font-semibold hover:bg-teal-700 disabled:opacity-60">
              {saving ? "Saving…" : category ? "Update" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ── Main AdminBlog component with tabs ───────────────────────────────────────
const AdminBlog = () => {
  const [activeTab, setActiveTab] = useState("posts");
  const { toast, show, dismiss } = useToast();

  // Posts state
  const [posts, setPosts] = useState([]);
  const [postsLoading, setPostsLoading] = useState(true);
  const [postsPage, setPostsPage] = useState(1);
  const [postsTotal, setPostsTotal] = useState(0);
  const [postsSearch, setPostsSearch] = useState("");
  const [postsSort, setPostsSort] = useState("-created_at");
  const [statusFilter, setStatusFilter] = useState("");
  const [catFilter, setCatFilter] = useState("");
  const [postModal, setPostModal] = useState(null);

  // Categories state
  const [categories, setCategories] = useState([]);
  const [catsLoading, setCatsLoading] = useState(true);
  const [catsPage, setCatsPage] = useState(1);
  const [catsTotal, setCatsTotal] = useState(0);
  const [catsSearch, setCatsSearch] = useState("");
  const [catModal, setCatModal] = useState(null);

  // Comments state
  const [comments, setComments] = useState([]);
  const [commentsLoading, setCommentsLoading] = useState(true);
  const [commentsPage, setCommentsPage] = useState(1);
  const [commentsTotal, setCommentsTotal] = useState(0);
  const [commentsSearch, setCommentsSearch] = useState("");
  const [approveFilter, setApproveFilter] = useState("");
  const [commentModal, setCommentModal] = useState(null); // for delete confirm

  // Common confirm state
  const [confirm, setConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // ── Fetch Posts ─────────────────────────────────────────────────────────
  const fetchPosts = () => {
    setPostsLoading(true);
    const params = {
      page: postsPage,
      page_size: 10,
      search: postsSearch || undefined,
      ordering: postsSort,
      status: statusFilter || undefined,
      category: catFilter || undefined,
    };
    adminAPI.getBlogPosts(params)
      .then(({ data }) => {
        setPosts(data.results ?? data);
        setPostsTotal(data.count ?? 0);
      })
      .catch(() => show("Failed to load posts", "error"))
      .finally(() => setPostsLoading(false));
  };

  useEffect(() => {
    if (activeTab === "posts") fetchPosts();
  }, [postsPage, postsSearch, postsSort, statusFilter, catFilter, activeTab]);

  // ── Fetch Categories ────────────────────────────────────────────────────
  const fetchCategories = () => {
    setCatsLoading(true);
    const params = { page: catsPage, page_size: 10, search: catsSearch || undefined };
    adminAPI.getBlogCategories(params)
      .then(({ data }) => {
        setCategories(data.results ?? data);
        setCatsTotal(data.count ?? 0);
      })
      .catch(() => show("Failed to load categories", "error"))
      .finally(() => setCatsLoading(false));
  };

  useEffect(() => {
    if (activeTab === "categories") fetchCategories();
  }, [catsPage, catsSearch, activeTab]);

  // ── Fetch Comments ──────────────────────────────────────────────────────
  const fetchComments = () => {
    setCommentsLoading(true);
    const params = {
      page: commentsPage,
      page_size: 10,
      search: commentsSearch || undefined,
      is_approved: approveFilter === "" ? undefined : approveFilter === "true",
    };
    adminAPI.getBlogComments(params)
      .then(({ data }) => {
        setComments(data.results ?? data);
        setCommentsTotal(data.count ?? 0);
      })
      .catch(() => show("Failed to load comments", "error"))
      .finally(() => setCommentsLoading(false));
  };

  useEffect(() => {
    if (activeTab === "comments") fetchComments();
  }, [commentsPage, commentsSearch, approveFilter, activeTab]);

  // ── Delete handlers ─────────────────────────────────────────────────────
  const handleDeletePost = async () => {
    setDeleting(true);
    try {
      await adminAPI.deleteBlogPost(confirm.id);
      show("Post deleted");
      setConfirm(null);
      fetchPosts();
    } catch {
      show("Failed to delete post", "error");
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteCategory = async () => {
    setDeleting(true);
    try {
      await adminAPI.deleteBlogCategory(confirm.id);
      show("Category deleted");
      setConfirm(null);
      fetchCategories();
    } catch {
      show("Failed to delete category", "error");
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteComment = async () => {
    setDeleting(true);
    try {
      await adminAPI.deleteBlogComment(confirm.id);
      show("Comment deleted");
      setConfirm(null);
      fetchComments();
    } catch {
      show("Failed to delete comment", "error");
    } finally {
      setDeleting(false);
    }
  };

  const handleApproveComment = async (id, currentApproved) => {
    try {
      await adminAPI.updateBlogComment(id, { is_approved: !currentApproved });
      show(currentApproved ? "Comment unapproved" : "Comment approved");
      fetchComments();
    } catch {
      show("Failed to update comment", "error");
    }
  };

  // ── Table column definitions ────────────────────────────────────────────
  const postColumns = [
    {
      key: "cover_image_url", label: "Cover",
      render: (url) => (
        <img src={url || "/assets/img/default-blog.jpg"} alt="cover"
          className="w-12 h-12 object-cover rounded-lg border" />
      ),
    },
    {
      key: "title", label: "Title", sortable: true,
      render: (v, row) => (
        <div>
          <p className="font-semibold text-gray-800 max-w-xs truncate">{v}</p>
          <p className="text-xs text-gray-500">{row.category_name} · {formatDate(row.created_at)}</p>
        </div>
      ),
    },
    {
      key: "status", label: "Status", sortable: true,
      render: (v) => statusBadge(v),
    },
    {
      key: "views_count", label: "Views", sortable: true,
      render: (v) => <span className="text-sm">{v || 0}</span>,
    },
    {
      key: "is_featured", label: "Featured",
      render: (v) => v ? <i className="bi bi-star-fill text-yellow-500"></i> : "—",
    },
  ];

  const categoryColumns = [
    {
      key: "name", label: "Name",
      render: (v, row) => (
        <div>
          <p className="font-medium text-gray-800">{v}</p>
          <p className="text-xs text-gray-400">slug: {row.slug}</p>
        </div>
      ),
    },
    {
      key: "posts_count", label: "Posts",
      render: (v) => <span className="text-sm">{v}</span>,
    },
  ];

  const commentColumns = [
    {
      key: "post_title", label: "Post",
      render: (v) => <p className="max-w-xs truncate text-sm font-medium">{v}</p>,
    },
    {
      key: "name", label: "Author",
      render: (v, row) => (
        <div>
          <p className="text-sm font-medium">{v}</p>
          <p className="text-xs text-gray-400">{row.email}</p>
        </div>
      ),
    },
    {
      key: "body", label: "Comment",
      render: (v) => <p className="text-sm max-w-md truncate">{v}</p>,
    },
    {
      key: "is_approved", label: "Approved",
      render: (v, row) => (
        <button onClick={() => handleApproveComment(row.id, v)}
          className={`text-xs px-2 py-1 rounded-full ${v ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}>
          {v ? "Approved" : "Pending"}
        </button>
      ),
    },
    {
      key: "created_at", label: "Date", sortable: true,
      render: (v) => formatDate(v),
    },
  ];

  const Btn = ({ icon, label, onClick, variant }) => (
    <button onClick={onClick} title={label}
      className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border transition ${
        variant === "danger"
          ? "border-red-200 text-red-600 hover:bg-red-50"
          : variant === "primary"
          ? "bg-teal-600 text-white border-teal-600 hover:bg-teal-700"
          : "border-gray-200 text-gray-600 hover:bg-gray-50"
      }`}>
      <i className={`bi ${icon}`}></i>
    </button>
  );

  const renderTabContent = () => {
    if (activeTab === "posts") {
      return (
        <DataTable
          columns={postColumns}
          data={posts}
          loading={postsLoading}
          totalCount={postsTotal}
          page={postsPage}
          pageSize={10}
          onPageChange={setPostsPage}
          sort={postsSort}
          onSort={setPostsSort}
          search={postsSearch}
          onSearch={(v) => { setPostsSearch(v); setPostsPage(1); }}
          searchPlaceholder="Search posts..."
          emptyIcon="bi-journal-bookmark"
          emptyText="No blog posts"
          filters={
            <div className="flex gap-2">
              <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPostsPage(1); }}
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm">
                <option value="">All status</option>
                <option value="draft">Draft</option>
                <option value="published">Published</option>
              </select>
              <select value={catFilter} onChange={(e) => { setCatFilter(e.target.value); setPostsPage(1); }}
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm">
                <option value="">All categories</option>
                {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          }
          rowActions={(row) => (
            <>
              <Btn icon="bi-pencil" label="Edit" onClick={() => setPostModal(row)} variant="primary" />
              <Btn icon="bi-trash" label="Delete" onClick={() => setConfirm({ id: row.id, name: row.title, type: "post" })} variant="danger" />
            </>
          )}
        />
      );
    }

    if (activeTab === "categories") {
      return (
        <DataTable
          columns={categoryColumns}
          data={categories}
          loading={catsLoading}
          totalCount={catsTotal}
          page={catsPage}
          pageSize={10}
          onPageChange={setCatsPage}
          search={catsSearch}
          onSearch={(v) => { setCatsSearch(v); setCatsPage(1); }}
          searchPlaceholder="Search categories..."
          emptyIcon="bi-tags"
          emptyText="No categories"
          rowActions={(row) => (
            <>
              <Btn icon="bi-pencil" label="Edit" onClick={() => setCatModal(row)} variant="primary" />
              <Btn icon="bi-trash" label="Delete" onClick={() => setConfirm({ id: row.id, name: row.name, type: "category" })} variant="danger" />
            </>
          )}
        />
      );
    }

    // Comments tab
    return (
      <DataTable
        columns={commentColumns}
        data={comments}
        loading={commentsLoading}
        totalCount={commentsTotal}
        page={commentsPage}
        pageSize={10}
        onPageChange={setCommentsPage}
        search={commentsSearch}
        onSearch={(v) => { setCommentsSearch(v); setCommentsPage(1); }}
        searchPlaceholder="Search by name, email or comment..."
        emptyIcon="bi-chat-dots"
        emptyText="No comments"
        filters={
          <select value={approveFilter} onChange={(e) => { setApproveFilter(e.target.value); setCommentsPage(1); }}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm">
            <option value="">All comments</option>
            <option value="true">Approved</option>
            <option value="false">Pending</option>
          </select>
        }
        rowActions={(row) => (
          <Btn icon="bi-trash" label="Delete" onClick={() => setConfirm({ id: row.id, name: `${row.name} on "${row.post_title}"`, type: "comment" })} variant="danger" />
        )}
      />
    );
  };

  const getConfirmDelete = () => {
    if (!confirm) return null;
    if (confirm.type === "post")
      return { message: `Delete post "${confirm.name}"? This action cannot be undone.`, onConfirm: handleDeletePost };
    if (confirm.type === "category")
      return { message: `Delete category "${confirm.name}"? Posts will remain but category will be set to null.`, onConfirm: handleDeleteCategory };
    return { message: `Delete comment by "${confirm.name}"?`, onConfirm: handleDeleteComment };
  };

  const confirmData = confirm ? getConfirmDelete() : null;

  return (
    <div className="space-y-5">
      <Toast toast={toast} onDismiss={dismiss} />

      {confirmData && (
        <ConfirmModal
          isOpen
          title="Delete"
          message={confirmData.message}
          confirmLabel="Delete"
          onConfirm={confirmData.onConfirm}
          onClose={() => setConfirm(null)}
          loading={deleting}
        />
      )}

      {postModal && (
        <PostModal
          post={postModal === "new" ? null : postModal}
          categories={categories}
          onClose={() => setPostModal(null)}
          onSaved={() => {
            fetchPosts();
            show("Post saved");
          }}
        />
      )}

      {catModal && (
        <CategoryModal
          category={catModal === "new" ? null : catModal}
          onClose={() => setCatModal(null)}
          onSaved={() => {
            fetchCategories();
            show("Category saved");
          }}
        />
      )}

      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Blog Management</h1>
          <p className="text-sm text-gray-500">Manage posts, categories and comments</p>
        </div>
        {activeTab === "posts" && (
          <button onClick={() => setPostModal("new")}
            className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-xl hover:bg-teal-700 transition text-sm font-semibold">
            <i className="bi bi-plus-lg"></i> New Post
          </button>
        )}
        {activeTab === "categories" && (
          <button onClick={() => setCatModal("new")}
            className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-xl hover:bg-teal-700 transition text-sm font-semibold">
            <i className="bi bi-plus-lg"></i> New Category
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4">
          {["posts", "categories", "comments"].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-2 px-1 text-sm font-medium capitalize transition ${
                activeTab === tab
                  ? "border-b-2 border-teal-600 text-teal-700"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {renderTabContent()}
    </div>
  );
};

export default AdminBlog;