/**
 * AdminMessages.test.jsx
 *
 * Comprehensive unit & integration tests for AdminMessages.jsx
 * Stack : Vitest · React Testing Library · @testing-library/user-event v14
 *
 * ── Coverage map ──────────────────────────────────────────────────────────────
 *  1.  Page structure        – heading, singular/plural subtitle, "unread"
 *                              badge conditional on total > 0
 *  2.  fetchMessages          – mount params (page/search/ordering/page_size),
 *                              loading state, paginated & flat response shapes,
 *                              count fallback to 0, error toast
 *  3.  Column renderers      – name (avatar initial + email), subject
 *                              ("(No subject)" fallback, 80-char preview + "…"),
 *                              created_at date formatting
 *  4.  Search                – re-fetch w/ search param, page reset to 1
 *  5.  Sort                  – re-fetch w/ new ordering
 *  6.  Pagination            – re-fetch w/ new page
 *  7.  Empty state           – "No messages yet"
 *  8.  Row actions            – "Read" opens MessagePanel, "Reply" mailto link
 *                              with encoded subject, "Delete" opens ConfirmModal
 *  9.  Delete – success      – ConfirmModal message w/ sender name,
 *                              deleteMessage(id), "Message deleted" toast,
 *                              closes confirm + selected, re-fetches
 * 10.  Delete – error        – error toast, modal stays open
 * 11.  Delete – cancel       – closes, no API call
 * 12.  Delete – in-flight    – confirm button disabled + "Deleting…" label
 * 13.  MessagePanel          – renders null when message is null, subject vs
 *                              "(No subject)", avatar initial vs "?" fallback,
 *                              name, email mailto link, formatted date, body
 *                              text, "Reply via Email" mailto link w/ encoded
 *                              subject, delete button → onDelete callback,
 *                              close (×) button, backdrop click closes, inner
 *                              panel click does NOT close
 * 14.  Panel → Delete wiring – clicking delete inside panel closes panel AND
 *                              opens ConfirmModal for that same message
 * 15.  Snapshot              – stable rendered output after data loads
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * ── Design notes (lessons applied from prior fixes) ──────────────────────────
 * • No debounce/timer logic in this component → plain userEvent.setup() only.
 * • "Delete" appears as both a row-action button AND inside MessagePanel —
 *   every interaction is scoped via within(row) / within(panel) to avoid
 *   ambiguous multi-match errors.
 * • Sender name/email are rendered inside the same flex row as other text
 *   (avatar initial, etc.) — assertions target the specific <p> leaf via
 *   within(cell) rather than a bare top-level getByText where collision risk
 *   exists.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  render,
  screen,
  waitFor,
  within,
  fireEvent,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminMessages from '../../pages/admin/AdminMessages';

// ─── Mock: DataTable ──────────────────────────────────────────────────────────
vi.mock('../../components/admin/DataTable', () => ({
  default: ({
    columns,
    data,
    loading,
    emptyText,
    rowActions,
    search,
    onSearch,
    onSort,
    onPageChange,
    searchPlaceholder,
    totalCount,
    page,
  }) => {
    if (loading) return <div data-testid="dt-loading">Loading…</div>;
    return (
      <div data-testid="data-table">
        <input
          data-testid="dt-search"
          placeholder={searchPlaceholder}
          value={search ?? ''}
          onChange={(e) => onSearch?.(e.target.value)}
        />
        <button data-testid="dt-sort" onClick={() => onSort?.('name')}>
          sort
        </button>
        <button
          data-testid="dt-next-page"
          onClick={() => onPageChange?.(page + 1)}
        >
          next
        </button>
        <span data-testid="dt-total">{totalCount}</span>

        {data.length === 0 && <div data-testid="dt-empty">{emptyText}</div>}

        {data.map((row, ri) => (
          <div key={row.id ?? ri} data-testid={`dt-row-${ri}`}>
            {columns.map((col) => (
              <div key={col.key} data-testid={`cell-${col.key}`}>
                {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '')}
              </div>
            ))}
            {rowActions && <div data-testid="row-actions">{rowActions(row)}</div>}
          </div>
        ))}
      </div>
    );
  },
}));

// ─── Mock: ConfirmModal ───────────────────────────────────────────────────────
vi.mock('../../components/admin/ConfirmModal', () => ({
  default: ({ isOpen, title, message, confirmLabel, onConfirm, onClose, loading }) =>
    isOpen ? (
      <div data-testid="confirm-modal">
        <p data-testid="confirm-title">{title}</p>
        <p data-testid="confirm-message">{message}</p>
        <button data-testid="confirm-btn" onClick={onConfirm} disabled={loading}>
          {loading ? 'Deleting…' : confirmLabel}
        </button>
        <button data-testid="confirm-cancel" onClick={onClose}>
          Cancel
        </button>
      </div>
    ) : null,
}));

// ─── Mock: Toast / useToast ───────────────────────────────────────────────────
let capturedToasts = [];

vi.mock('../../components/admin/Toast', () => ({
  default: ({ toast, onDismiss }) =>
    toast ? (
      <div data-testid="toast" data-type={toast.type}>
        {toast.message}
        <button data-testid="toast-dismiss" onClick={onDismiss}>×</button>
      </div>
    ) : null,
  useToast: () => ({
    toast: null,
    show: (message, type = 'success') => {
      capturedToasts.push({ message, type });
    },
    dismiss: () => { },
  }),
}));

// ─── Mock: adminAPI ───────────────────────────────────────────────────────────
vi.mock('../../services/api', () => ({
  adminAPI: {
    getMessages: vi.fn(),
    deleteMessage: vi.fn(),
  },
}));
import { adminAPI } from '../../services/api';

// ─── Fixture factories ────────────────────────────────────────────────────────
const makeMessage = (overrides = {}) => ({
  id: 1,
  name: 'Alice Johnson',
  email: 'alice@example.com',
  subject: 'Question about pricing',
  message: 'Hi, I wanted to ask about your enterprise pricing tiers.',
  created_at: '2024-06-01T10:30:00Z',
  ...overrides,
});

const makeMessages = (n = 3) =>
  Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    name: `Sender ${i + 1}`,
    email: `sender${i + 1}@test.com`,
    subject: `Subject ${i + 1}`,
    message: `Message body number ${i + 1}. `.repeat(10), // long body for slice test
    created_at: '2024-06-01T10:30:00Z',
  }));

const paged = (results, count) => ({ data: { results, count } });
const flat = (arr) => ({ data: arr });

const okMessages = (msgs = makeMessages()) =>
  adminAPI.getMessages.mockResolvedValue(paged(msgs, msgs.length));

const setup = () => userEvent.setup();

/** The slide-out panel card (inner div that stops propagation). */
const getPanelCard = () =>
  document.querySelector('.fixed.inset-0.flex.justify-end .bg-white');

// ─────────────────────────────────────────────────────────────────────────────

describe('AdminMessages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedToasts = [];
    okMessages();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── 1. Page structure ────────────────────────────────────────────────────
  describe('Page structure', () => {
    it('renders the "Contact Messages" heading', () => {
      render(<AdminMessages />);
      expect(
        screen.getByRole('heading', { name: /contact messages/i })
      ).toBeInTheDocument();
    });

    it('shows plural subtitle when total !== 1', async () => {
      okMessages(makeMessages(5));
      render(<AdminMessages />);
      await waitFor(() =>
        expect(screen.getByText('5 messages in inbox')).toBeInTheDocument()
      );
    });

    it('shows singular subtitle when total === 1', async () => {
      okMessages([makeMessage()]);
      render(<AdminMessages />);
      await waitFor(() =>
        expect(screen.getByText('1 message in inbox')).toBeInTheDocument()
      );
    });

    it('shows "0 messages in inbox" when total is 0', async () => {
      adminAPI.getMessages.mockResolvedValue(paged([], 0));
      render(<AdminMessages />);
      await waitFor(() =>
        expect(screen.getByText('0 messages in inbox')).toBeInTheDocument()
      );
    });

    it('shows the "unread" badge when total > 0', async () => {
      okMessages(makeMessages(4));
      render(<AdminMessages />);
      await waitFor(() =>
        expect(screen.getByText('4 unread')).toBeInTheDocument()
      );
    });

    it('hides the "unread" badge when total is 0', async () => {
      adminAPI.getMessages.mockResolvedValue(paged([], 0));
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('0 messages in inbox'));
      expect(screen.queryByText(/unread/)).not.toBeInTheDocument();
    });
  });

  // ── 2. fetchMessages ──────────────────────────────────────────────────────
  describe('fetchMessages – initial fetch', () => {
    it('calls getMessages on mount with correct default params', async () => {
      render(<AdminMessages />);
      await waitFor(() =>
        expect(adminAPI.getMessages).toHaveBeenCalledWith({
          page: 1,
          search: '',
          ordering: '-created_at',
          page_size: 12,
        })
      );
    });

    it('shows loading indicator while fetch is in-flight', () => {
      adminAPI.getMessages.mockReturnValue(new Promise(() => { }));
      render(<AdminMessages />);
      expect(screen.getByTestId('dt-loading')).toBeInTheDocument();
    });

    it('clears loading state after data resolves', async () => {
      render(<AdminMessages />);
      await waitFor(() =>
        expect(screen.queryByTestId('dt-loading')).not.toBeInTheDocument()
      );
    });

    it('clears loading state even after API error', async () => {
      adminAPI.getMessages.mockRejectedValue(new Error('net'));
      render(<AdminMessages />);
      await waitFor(() =>
        expect(screen.queryByTestId('dt-loading')).not.toBeInTheDocument()
      );
    });

    it('renders message rows from a paginated response', async () => {
      render(<AdminMessages />);
      await waitFor(() => {
        expect(screen.getByText('Sender 1')).toBeInTheDocument();
        expect(screen.getByText('Sender 2')).toBeInTheDocument();
        expect(screen.getByText('Sender 3')).toBeInTheDocument();
      });
    });

    it('handles a flat (non-paginated) array response', async () => {
      adminAPI.getMessages.mockResolvedValue(flat(makeMessages(2)));
      render(<AdminMessages />);
      await waitFor(() => {
        expect(screen.getByText('Sender 1')).toBeInTheDocument();
        expect(screen.getByText('Sender 2')).toBeInTheDocument();
      });
    });

    it('falls back total to 0 for flat-array response (not array length)', async () => {
      adminAPI.getMessages.mockResolvedValue(flat(makeMessages(5)));
      render(<AdminMessages />);
      await waitFor(() =>
        expect(screen.getByTestId('dt-total').textContent).toBe('0')
      );
    });

    it('sets total from paginated count field', async () => {
      adminAPI.getMessages.mockResolvedValue(paged(makeMessages(3), 27));
      render(<AdminMessages />);
      await waitFor(() =>
        expect(screen.getByTestId('dt-total').textContent).toBe('27')
      );
    });

    it('shows "Failed to load messages" error toast on API failure', async () => {
      adminAPI.getMessages.mockRejectedValue(new Error('net'));
      render(<AdminMessages />);
      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === 'Failed to load messages' && t.type === 'error'
          )
        ).toBe(true)
      );
    });
  });

  // ── 3. Column renderers ──────────────────────────────────────────────────
  describe('Column renderers', () => {
    describe('name column', () => {
      it("renders the sender's name", async () => {
        adminAPI.getMessages.mockResolvedValue(
          paged([makeMessage({ name: 'Bob Wilson' })], 1)
        );
        render(<AdminMessages />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-name');
          expect(within(cell).getByText('Bob Wilson')).toBeInTheDocument();
        });
      });

      it('renders the uppercase first-letter avatar initial', async () => {
        adminAPI.getMessages.mockResolvedValue(
          paged([makeMessage({ name: 'bob wilson' })], 1)
        );
        render(<AdminMessages />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-name');
          expect(within(cell).getByText('B')).toBeInTheDocument();
        });
      });

      it("renders the sender's email beneath the name", async () => {
        adminAPI.getMessages.mockResolvedValue(
          paged([makeMessage({ email: 'bob@test.com' })], 1)
        );
        render(<AdminMessages />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-name');
          expect(within(cell).getByText('bob@test.com')).toBeInTheDocument();
        });
      });
    });

    describe('subject column', () => {
      it('renders the subject text when present', async () => {
        adminAPI.getMessages.mockResolvedValue(
          paged([makeMessage({ subject: 'Billing issue' })], 1)
        );
        render(<AdminMessages />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-subject');
          expect(within(cell).getByText('Billing issue')).toBeInTheDocument();
        });
      });

      it('renders "(No subject)" when subject is empty', async () => {
        adminAPI.getMessages.mockResolvedValue(
          paged([makeMessage({ subject: '' })], 1)
        );
        render(<AdminMessages />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-subject');
          expect(within(cell).getByText('(No subject)')).toBeInTheDocument();
        });
      });

      it('renders "(No subject)" when subject is null', async () => {
        adminAPI.getMessages.mockResolvedValue(
          paged([makeMessage({ subject: null })], 1)
        );
        render(<AdminMessages />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-subject');
          expect(within(cell).getByText('(No subject)')).toBeInTheDocument();
        });
      });

      it('truncates the message preview to 80 characters with an ellipsis', async () => {
        const longMessage = 'A'.repeat(200);
        adminAPI.getMessages.mockResolvedValue(
          paged([makeMessage({ message: longMessage })], 1)
        );
        render(<AdminMessages />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-subject');
          const preview = within(cell).getByText(/^A{80}…$/);
          expect(preview).toBeInTheDocument();
          // Confirm exactly 80 A's, not 81 or 79
          expect(preview.textContent).toBe('A'.repeat(80) + '…');
        });
      });
    });

    describe('created_at column', () => {
      it('formats the ISO date string', async () => {
        adminAPI.getMessages.mockResolvedValue(
          paged([makeMessage({ created_at: '2024-06-15T00:00:00Z' })], 1)
        );
        render(<AdminMessages />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-created_at');
          // Locale-dependent formatting; just confirm it's a non-ISO date string
          expect(cell.textContent).toMatch(/\d/);
          expect(cell.textContent).not.toContain('T');
        });
      });
    });
  });

  // ── 4. Search ────────────────────────────────────────────────────────────
  describe('Search', () => {
    it('re-fetches with the typed search string', async () => {
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));

      vi.clearAllMocks();
      okMessages();

      const searchInput = screen.getByPlaceholderText('Search by name, email, subject…');
      fireEvent.change(searchInput, { target: { value: 'pricing' } });

      await waitFor(() =>
        expect(adminAPI.getMessages).toHaveBeenLastCalledWith(
          expect.objectContaining({ search: 'pricing' })
        )
      );
    });

    it('resets page to 1 when search changes', async () => {
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));

      await user.click(screen.getByTestId('dt-next-page'));
      await waitFor(() =>
        expect(adminAPI.getMessages).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );

      vi.clearAllMocks();
      okMessages();

      const searchInput = screen.getByPlaceholderText('Search by name, email, subject…');
      fireEvent.change(searchInput, { target: { value: 'x' } });

      await waitFor(() =>
        expect(adminAPI.getMessages).toHaveBeenLastCalledWith(
          expect.objectContaining({ page: 1, search: 'x' })
        )
      );
    });
  });

  // ── 5. Sort ──────────────────────────────────────────────────────────────
  describe('Sort', () => {
    it('re-fetches with new ordering when sort changes', async () => {
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));

      vi.clearAllMocks();
      okMessages();

      await user.click(screen.getByTestId('dt-sort'));

      await waitFor(() =>
        expect(adminAPI.getMessages).toHaveBeenCalledWith(
          expect.objectContaining({ ordering: 'name' })
        )
      );
    });
  });

  // ── 6. Pagination ────────────────────────────────────────────────────────
  describe('Pagination', () => {
    it('re-fetches with incremented page when next-page triggered', async () => {
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));

      vi.clearAllMocks();
      okMessages();

      await user.click(screen.getByTestId('dt-next-page'));

      await waitFor(() =>
        expect(adminAPI.getMessages).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );
    });
  });

  // ── 7. Empty state ───────────────────────────────────────────────────────
  describe('Empty state', () => {
    it('shows "No messages yet" when results are empty', async () => {
      adminAPI.getMessages.mockResolvedValue(paged([], 0));
      render(<AdminMessages />);
      await waitFor(() =>
        expect(screen.getByTestId('dt-empty')).toHaveTextContent('No messages yet')
      );
    });
  });

  // ── 8. Row actions ───────────────────────────────────────────────────────
  describe('Row actions', () => {
    it('"Read" button opens the MessagePanel for that row', async () => {
      adminAPI.getMessages.mockResolvedValue(
        paged([makeMessage({ name: 'Carol Diaz' })], 1)
      );
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Carol Diaz'));

      await user.click(
        within(screen.getByTestId('dt-row-0')).getByTitle('Read')
      );

      await waitFor(() => {
        const panel = getPanelCard();
        expect(within(panel).getByText('Carol Diaz')).toBeInTheDocument();
      });
    });

    it('"Reply" link has the correct mailto href with encoded subject', async () => {
      adminAPI.getMessages.mockResolvedValue(
        paged([makeMessage({ email: 'carol@test.com', subject: 'Pricing & Plans' })], 1)
      );
      render(<AdminMessages />);
      await waitFor(() => {
        const replyLink = within(screen.getByTestId('dt-row-0')).getByTitle('Reply');
        expect(replyLink).toHaveAttribute(
          'href',
          `mailto:carol@test.com?subject=Re: ${encodeURIComponent('Pricing & Plans')}`
        );
      });
    });

    it('"Reply" link handles empty subject gracefully', async () => {
      adminAPI.getMessages.mockResolvedValue(
        paged([makeMessage({ email: 'carol@test.com', subject: '' })], 1)
      );
      render(<AdminMessages />);
      await waitFor(() => {
        const replyLink = within(screen.getByTestId('dt-row-0')).getByTitle('Reply');
        expect(replyLink).toHaveAttribute('href', 'mailto:carol@test.com?subject=Re: ');
      });
    });

    it('"Delete" row action opens ConfirmModal', async () => {
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));
      await user.click(
        within(screen.getByTestId('dt-row-0')).getByTitle('Delete')
      );
      await waitFor(() =>
        expect(screen.getByTestId('confirm-modal')).toBeInTheDocument()
      );
    });
  });

  // ── 9. Delete – success ──────────────────────────────────────────────────
  describe('Delete – success', () => {
    const openConfirmFromRow = async (user) => {
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));
      await user.click(
        within(screen.getByTestId('dt-row-0')).getByTitle('Delete')
      );
    };

    it('ConfirmModal title is "Delete Message"', async () => {
      const user = setup();
      await openConfirmFromRow(user);
      expect(screen.getByTestId('confirm-title')).toHaveTextContent('Delete Message');
    });

    it('ConfirmModal message includes the sender name', async () => {
      const user = setup();
      await openConfirmFromRow(user);
      expect(screen.getByTestId('confirm-message')).toHaveTextContent(
        'Permanently delete the message from "Sender 1"?'
      );
    });

    it('calls deleteMessage with the correct id on confirm', async () => {
      adminAPI.deleteMessage.mockResolvedValue({});
      const user = setup();
      await openConfirmFromRow(user);
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(adminAPI.deleteMessage).toHaveBeenCalledWith(1)
      );
    });

    it('shows "Message deleted" success toast', async () => {
      adminAPI.deleteMessage.mockResolvedValue({});
      const user = setup();
      await openConfirmFromRow(user);
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === 'Message deleted' && t.type === 'success')
        ).toBe(true)
      );
    });

    it('closes ConfirmModal after successful delete', async () => {
      adminAPI.deleteMessage.mockResolvedValue({});
      const user = setup();
      await openConfirmFromRow(user);
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(screen.queryByTestId('confirm-modal')).not.toBeInTheDocument()
      );
    });

    it('also clears selected (closes MessagePanel) after successful delete', async () => {
      // Open panel first, then delete from inside the panel
      adminAPI.deleteMessage.mockResolvedValue({});
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Read'));
      await waitFor(() => getPanelCard());

      const panel = getPanelCard();

      const trashBtn = panel.querySelector('.bi-trash').closest('button');
      await user.click(trashBtn);

      await waitFor(() => screen.getByTestId('confirm-modal'));
      await user.click(screen.getByTestId('confirm-btn'));

      await waitFor(() => {
        expect(screen.queryByTestId('confirm-modal')).not.toBeInTheDocument();
        expect(getPanelCard()).not.toBeInTheDocument();
      });
    });

    it('re-fetches message list after successful delete', async () => {
      adminAPI.deleteMessage.mockResolvedValue({});
      const user = setup();
      await openConfirmFromRow(user);

      vi.clearAllMocks();
      okMessages();

      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(adminAPI.getMessages).toHaveBeenCalledTimes(1)
      );
    });
  });

  // ── 10. Delete – error ───────────────────────────────────────────────────
  describe('Delete – error', () => {
    it('shows "Failed to delete message" error toast when deleteMessage rejects', async () => {
      adminAPI.deleteMessage.mockRejectedValue(new Error('500'));
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === 'Failed to delete message' && t.type === 'error'
          )
        ).toBe(true)
      );
    });

    it('keeps ConfirmModal open after a failed delete', async () => {
      adminAPI.deleteMessage.mockRejectedValue(new Error('500'));
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(screen.getByTestId('confirm-modal')).toBeInTheDocument()
      );
    });
  });

  // ── 11. Delete – cancel ──────────────────────────────────────────────────
  describe('Delete – cancel', () => {
    it('closes ConfirmModal when Cancel is clicked', async () => {
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await user.click(screen.getByTestId('confirm-cancel'));
      await waitFor(() =>
        expect(screen.queryByTestId('confirm-modal')).not.toBeInTheDocument()
      );
    });

    it('does NOT call deleteMessage when Cancel is clicked', async () => {
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await user.click(screen.getByTestId('confirm-cancel'));
      expect(adminAPI.deleteMessage).not.toHaveBeenCalled();
    });
  });

  // ── 12. Delete – in-flight state ─────────────────────────────────────────
  describe('Delete – in-flight state', () => {
    const pendingDelete = () => {
      let resolve;
      adminAPI.deleteMessage.mockReturnValue(new Promise((r) => { resolve = r; }));
      return resolve;
    };

    it('disables confirm button while delete is in-flight', async () => {
      const resolve = pendingDelete();
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(screen.getByTestId('confirm-btn')).toBeDisabled()
      );
      resolve({});
    });

    it('shows "Deleting…" label on confirm button while in-flight', async () => {
      const resolve = pendingDelete();
      const user = setup();
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(screen.getByTestId('confirm-btn')).toHaveTextContent('Deleting…')
      );
      resolve({});
    });
  });

  // ── 13. MessagePanel ─────────────────────────────────────────────────────
  describe('MessagePanel', () => {
    const openPanel = async (user, message = makeMessage()) => {
      adminAPI.getMessages.mockResolvedValue(paged([message], 1));
      render(<AdminMessages />);
      await waitFor(() => {
        expect(screen.queryByTestId('dt-loading')).not.toBeInTheDocument();
      });
      const row = screen.getByTestId('dt-row-0');
      const nameEl = within(row).getByText((content, el) => {
        return content === message.name && el.tagName.toLowerCase() === 'p';
      });
      expect(nameEl).toBeInTheDocument();
      await user.click(within(row).getByTitle('Read'));
      await waitFor(() => getPanelCard());
    };

    it('renders nothing when no message is selected', () => {
      render(<AdminMessages />);
      expect(getPanelCard()).not.toBeInTheDocument();
    });

    it('shows the subject in the panel header', async () => {
      const user = setup();
      await openPanel(user, makeMessage({ subject: 'Partnership inquiry' }));
      const panel = getPanelCard();
      expect(within(panel).getByText('Partnership inquiry')).toBeInTheDocument();
    });

    it('shows "(No subject)" in the header when subject is empty', async () => {
      const user = setup();
      await openPanel(user, makeMessage({ subject: '' }));
      const panel = getPanelCard();
      expect(within(panel).getByText('(No subject)')).toBeInTheDocument();
    });

    it("renders the sender's name", async () => {
      const user = setup();
      await openPanel(user, makeMessage({ name: 'Derek Lee' }));
      const panel = getPanelCard();
      expect(within(panel).getByText('Derek Lee')).toBeInTheDocument();
    });

    it('renders the uppercase avatar initial from the name', async () => {
      const user = setup();
      await openPanel(user, makeMessage({ name: 'derek lee' }));
      const panel = getPanelCard();
      expect(within(panel).getByText('D')).toBeInTheDocument();
    });

    it('renders "?" avatar fallback when name is falsy', async () => {
      const user = setup();
      await openPanel(user, makeMessage({ name: '' }));
      const panel = getPanelCard();
      expect(within(panel).getByText('?')).toBeInTheDocument();
    });

    it('renders the email as a mailto link', async () => {
      const user = setup();
      await openPanel(user, makeMessage({ email: 'derek@test.com' }));
      const panel = getPanelCard();
      const emailLink = within(panel).getByText('derek@test.com');
      expect(emailLink).toHaveAttribute('href', 'mailto:derek@test.com');
    });

    it('renders the formatted received date', async () => {
      const user = setup();
      await openPanel(user, makeMessage({ created_at: '2024-03-10T00:00:00Z' }));
      const panel = getPanelCard();
      // Locale-dependent; just confirm a non-ISO date-looking string
      expect(within(panel).getByText(/2024/)).toBeInTheDocument();
    });

    it('renders the full message body text', async () => {
      const user = setup();
      const fullBody = 'This is the complete message body with full details.';
      await openPanel(user, makeMessage({ message: fullBody }));
      const panel = getPanelCard();
      expect(within(panel).getByText(fullBody)).toBeInTheDocument();
    });

    it('preserves whitespace in the message body (whitespace-pre-wrap)', async () => {
      const user = setup();
      const multiline = 'Line one\nLine two';
      await openPanel(user, makeMessage({ message: multiline }));
      const panel = getPanelCard();

      // 1. Grab the container using a partial text match or regex
      const bodyEl = within(panel).getByText(/Line one/);

      // 2. Assert both the exact text structure and the tailwind class
      expect(bodyEl.textContent).toBe(multiline);
      expect(bodyEl.className).toMatch(/whitespace-pre-wrap/);
    });

    it('"Reply via Email" link has the correct mailto href', async () => {
      const user = setup();
      await openPanel(user, makeMessage({ email: 'derek@test.com', subject: 'Hello there' }));
      const panel = getPanelCard();
      const replyLink = within(panel).getByRole('link', { name: /reply via email/i });
      expect(replyLink).toHaveAttribute(
        'href',
        `mailto:derek@test.com?subject=Re: ${encodeURIComponent('Hello there')}`
      );
    });

    it('closes the panel when the × button is clicked', async () => {
      const user = setup();
      await openPanel(user);
      const panel = getPanelCard();
      const closeBtn = panel.parentElement.querySelector('.bi-x-lg').closest('button');
      await user.click(closeBtn);
      await waitFor(() => expect(getPanelCard()).not.toBeInTheDocument());
    });

    it('closes the panel when the backdrop is clicked', async () => {
      const user = setup();
      await openPanel(user);
      const backdrop = document.querySelector('.fixed.inset-0.flex.justify-end');
      fireEvent.click(backdrop);
      await waitFor(() => expect(getPanelCard()).not.toBeInTheDocument());
    });

    it('clicking inside the panel does NOT close it', async () => {
      const user = setup();
      await openPanel(user);
      const panel = getPanelCard();
      fireEvent.click(panel);
      expect(getPanelCard()).toBeInTheDocument();
    });
  });

  // ── 14. Panel → Delete wiring ─────────────────────────────────────────────
  describe('MessagePanel delete wiring', () => {
    it('clicking the trash icon in the panel closes the panel and opens ConfirmModal', async () => {
      const user = setup();
      adminAPI.getMessages.mockResolvedValue(
        paged([makeMessage({ name: 'Erin Park' })], 1)
      );
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Erin Park'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Read'));

      const panel = getPanelCard();
      await waitFor(() => within(panel).getByText('Erin Park'));

      const trashBtn = panel.querySelector('.bi-trash').closest('button');
      await user.click(trashBtn);

      await waitFor(() => {
        expect(getPanelCard()).not.toBeInTheDocument();
        expect(screen.getByTestId('confirm-modal')).toBeInTheDocument();
      });
    });

    it('ConfirmModal opened from the panel references the correct message', async () => {
      const user = setup();
      adminAPI.getMessages.mockResolvedValue(
        paged([makeMessage({ name: 'Erin Park' })], 1)
      );
      render(<AdminMessages />);
      await waitFor(() => screen.getByText('Erin Park'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Read'));

      const panel = getPanelCard();
      const trashBtn = panel.querySelector('.bi-trash').closest('button');
      await user.click(trashBtn);

      await waitFor(() =>
        expect(screen.getByTestId('confirm-message')).toHaveTextContent(
          'Permanently delete the message from "Erin Park"?'
        )
      );
    });
  });

  // ── 15. Snapshot ─────────────────────────────────────────────────────────
  describe('Snapshot', () => {
    it('matches stable snapshot after data loads', async () => {
      const { asFragment } = render(<AdminMessages />);
      await waitFor(() => screen.getByText('Sender 1'));
      expect(asFragment()).toMatchSnapshot();
    });
  });
});
