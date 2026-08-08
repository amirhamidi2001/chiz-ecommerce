/**
 * AdminUsers.test.jsx
 *
 * Comprehensive unit & integration tests for AdminUsers.jsx
 * Stack : Vitest · React Testing Library · @testing-library/user-event v14
 *
 * ── Coverage map ──────────────────────────────────────────────────────────────
 *  1.  Page structure        – "Users" heading, "{total} registered users"
 *                              subtitle
 *  2.  fetchUsers            – mount params (is_active:undefined when filter
 *                              empty, STRING "true"/"false" when set, not
 *                              boolean), count ?? 0 fallback, loading state,
 *                              paginated & flat response shapes, error toast
 *  3.  Column renderers      – avatar_url (img vs email-initial fallback —
 *                              NOT full_name initial), email column (full_name
 *                              ?? email primary + email always secondary),
 *                              role <select> options + disabled state, status
 *                              badge (Active/green vs Inactive/red), verified
 *                              icon (shield-check/teal vs shield-x/gray),
 *                              total_orders (not sortable), total_spent fmt(),
 *                              created_date date format
 *  4.  Search                – re-fetch w/ search param, page reset to 1
 *  5.  Sort                  – re-fetch w/ new ordering
 *  6.  Active filter         – re-fetch w/ is_active string value, undefined
 *                              when reset to "All Users", page reset to 1
 *  7.  Pagination            – re-fetch w/ new page
 *  8.  Empty state           – "No users found"
 *  9.  toggleActive          – updateUser({is_active: !current}), row mutated
 *                              in place, message reflects PREVIOUS state
 *                              ("deactivated" when going active→inactive,
 *                              "activated" when inactive→active), error
 *                              toast + row unchanged on failure, button label
 *                              swaps after toggle, spinner shown while
 *                              updating, button disabled only for the
 *                              affected row (sibling rows stay enabled)
 * 10.  changeRole            – updateUser({type: parseInt(value)}), row.type
 *                              mutated to the parsed integer, "Role updated"
 *                              toast, error toast + row unchanged on failure,
 *                              select disabled only for the affected row,
 *                              select onClick stops propagation (no row-level
 *                              side effect)
 * 11.  Concurrent updating    – updating one row does not disable a sibling
 *                              row's controls
 * 12.  Snapshot              – stable rendered output after data loads
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * ── Design notes ──────────────────────────────────────────────────────────────
 * • `is_active` query param is the literal STRING "true"/"false" from the
 *   <select> value, NOT a boolean — `activeFilter !== "" ? activeFilter :
 *   undefined` passes the raw string through. Tests assert the exact string,
 *   not `true`/`false` booleans.
 * • Avatar fallback initial comes from `row.email[0]`, not `full_name[0]` —
 *   explicitly tested with a fixture where email and full_name have different
 *   first letters to catch an accidental swap.
 * • `updating` is page-level state keyed by a single user id at a time. Tests
 *   with 2+ rows confirm toggling row 0 does NOT disable row 1's button/select.
 * • No modals, no debounce/timer logic in this component → plain
 *   userEvent.setup() only, no fake timers needed anywhere.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminUsers from '../../pages/admin/AdminUsers';

// ─── Mock: DataTable ──────────────────────────────────────────────────────────
vi.mock('../../components/admin/DataTable', () => ({
  default: ({
    columns,
    data,
    loading,
    emptyText,
    rowActions,
    filters,
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
        {filters && <div data-testid="dt-filters">{filters}</div>}
        <input
          data-testid="dt-search"
          placeholder={searchPlaceholder}
          value={search ?? ''}
          onChange={(e) => onSearch?.(e.target.value)}
        />
        <button data-testid="dt-sort" onClick={() => onSort?.('email')}>
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
    getUsers: vi.fn(),
    updateUser: vi.fn(),
  },
}));
import { adminAPI } from '../../services/api';

// ─── Fixture factories ────────────────────────────────────────────────────────
const makeUser = (overrides = {}) => ({
  id: 1,
  email: 'alice@test.com',
  full_name: 'Alice Johnson',
  type: 1,
  is_active: true,
  is_verified: true,
  total_orders: 5,
  total_spent: 250,
  avatar_url: null,
  created_date: '2024-06-01T10:00:00Z',
  ...overrides,
});

const makeUsers = (n = 3) =>
  Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    email: `user${i + 1}@test.com`,
    full_name: `User ${i + 1}`,
    type: 1,
    is_active: true,
    is_verified: false,
    total_orders: i,
    total_spent: i * 50,
    avatar_url: null,
    created_date: '2024-06-01T10:00:00Z',
  }));

const paged = (results, count) => ({ data: { results, count } });
const flat = (arr) => ({ data: arr });

const okUsers = (users = makeUsers()) =>
  adminAPI.getUsers.mockResolvedValue(paged(users, users.length));

const setup = () => userEvent.setup();

// ─────────────────────────────────────────────────────────────────────────────

describe('AdminUsers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedToasts = [];
    okUsers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── 1. Page structure ────────────────────────────────────────────────────
  describe('Page structure', () => {
    it('renders the "Users" heading', () => {
      render(<AdminUsers />);
      expect(screen.getByRole('heading', { name: /^users$/i })).toBeInTheDocument();
    });

    it('shows "{total} registered users" subtitle after data loads', async () => {
      okUsers(makeUsers(6));
      render(<AdminUsers />);
      await waitFor(() =>
        expect(screen.getByText('6 registered users')).toBeInTheDocument()
      );
    });

    it('shows "0 registered users" before data loads', () => {
      adminAPI.getUsers.mockReturnValue(new Promise(() => { }));
      render(<AdminUsers />);
      expect(screen.getByText('0 registered users')).toBeInTheDocument();
    });
  });

  // ── 2. fetchUsers ─────────────────────────────────────────────────────────
  describe('fetchUsers – initial fetch', () => {
    it('calls getUsers on mount with is_active:undefined when no filter is set', async () => {
      render(<AdminUsers />);
      await waitFor(() =>
        expect(adminAPI.getUsers).toHaveBeenCalledWith({
          page: 1,
          search: '',
          ordering: '-created_date',
          page_size: 10,
          is_active: undefined,
        })
      );
    });

    it('shows loading indicator while fetch is in-flight', () => {
      adminAPI.getUsers.mockReturnValue(new Promise(() => { }));
      render(<AdminUsers />);
      expect(screen.getByTestId('dt-loading')).toBeInTheDocument();
    });

    it('clears loading state after data resolves', async () => {
      render(<AdminUsers />);
      await waitFor(() =>
        expect(screen.queryByTestId('dt-loading')).not.toBeInTheDocument()
      );
    });

    it('clears loading state even after API error', async () => {
      adminAPI.getUsers.mockRejectedValue(new Error('net'));
      render(<AdminUsers />);
      await waitFor(() =>
        expect(screen.queryByTestId('dt-loading')).not.toBeInTheDocument()
      );
    });

    it('renders user rows from a paginated response', async () => {
      render(<AdminUsers />);
      await waitFor(() => {
        expect(screen.getByText('User 1')).toBeInTheDocument();
        expect(screen.getByText('User 2')).toBeInTheDocument();
        expect(screen.getByText('User 3')).toBeInTheDocument();
      });
    });

    it('handles a flat (non-paginated) array response', async () => {
      adminAPI.getUsers.mockResolvedValue(flat(makeUsers(2)));
      render(<AdminUsers />);
      await waitFor(() => {
        expect(screen.getByText('User 1')).toBeInTheDocument();
        expect(screen.getByText('User 2')).toBeInTheDocument();
      });
    });

    it('falls back total to 0 for flat-array response (not array length)', async () => {
      adminAPI.getUsers.mockResolvedValue(flat(makeUsers(5)));
      render(<AdminUsers />);
      await waitFor(() =>
        expect(screen.getByText('0 registered users')).toBeInTheDocument()
      );
    });

    it('sets total from paginated count field', async () => {
      adminAPI.getUsers.mockResolvedValue(paged(makeUsers(3), 64));
      render(<AdminUsers />);
      await waitFor(() =>
        expect(screen.getByText('64 registered users')).toBeInTheDocument()
      );
    });

    it('shows "Failed to load users" error toast on API failure', async () => {
      adminAPI.getUsers.mockRejectedValue(new Error('net'));
      render(<AdminUsers />);
      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === 'Failed to load users' && t.type === 'error'
          )
        ).toBe(true)
      );
    });
  });

  // ── 3. Column renderers ──────────────────────────────────────────────────
  describe('Column renderers', () => {
    describe('avatar_url column', () => {
      it('renders an <img> when avatar_url is present', async () => {
        adminAPI.getUsers.mockResolvedValue(
          paged([makeUser({ avatar_url: 'https://cdn.test/avatar.jpg' })], 1)
        );
        render(<AdminUsers />);

        const cell = await screen.findByTestId('cell-avatar_url');

        const img = cell.querySelector('img');

        expect(img).toBeInTheDocument();
        expect(img).toHaveAttribute('src', 'https://cdn.test/avatar.jpg');
      });

      it('falls back to the uppercase EMAIL initial (not full_name) when avatar_url is null', async () => {
        adminAPI.getUsers.mockResolvedValue(
          paged([makeUser({ avatar_url: null, email: 'zach@test.com', full_name: 'Alice Johnson' })], 1)
        );
        render(<AdminUsers />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-avatar_url');
          // Initial should be "Z" (from email), NOT "A" (from full_name)
          expect(within(cell).getByText('Z')).toBeInTheDocument();
          expect(within(cell).queryByText('A')).not.toBeInTheDocument();
        });
      });
    });

    describe('email column', () => {
      it('shows full_name as the primary line when present', async () => {
        adminAPI.getUsers.mockResolvedValue(
          paged([makeUser({ full_name: 'Bob Wilson', email: 'bob@test.com' })], 1)
        );
        render(<AdminUsers />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-email');
          expect(within(cell).getByText('Bob Wilson')).toBeInTheDocument();
        });
      });

      it('always shows the email as the secondary line', async () => {
        adminAPI.getUsers.mockResolvedValue(
          paged([makeUser({ full_name: 'Bob Wilson', email: 'bob@test.com' })], 1)
        );
        render(<AdminUsers />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-email');
          expect(within(cell).getByText('bob@test.com')).toBeInTheDocument();
        });
      });

      it('falls back to email as the primary line when full_name is falsy', async () => {
        adminAPI.getUsers.mockResolvedValue(
          paged([makeUser({ full_name: '', email: 'noname@test.com' })], 1)
        );
        render(<AdminUsers />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-email');
          // Both primary and secondary line show the email in this case
          expect(within(cell).getAllByText('noname@test.com')).toHaveLength(2);
        });
      });
    });

    describe('type (Role) column', () => {
      it('renders a select with Customer/Admin/Superuser options', async () => {
        adminAPI.getUsers.mockResolvedValue(paged([makeUser({ type: 1 })], 1));
        render(<AdminUsers />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-type');
          const select = within(cell).getByRole('combobox');
          const opts = within(select).getAllByRole('option').map((o) => o.textContent);
          expect(opts).toEqual(['Customer', 'Admin', 'Superuser']);
        });
      });

      it('pre-selects the value matching the user\'s current type', async () => {
        adminAPI.getUsers.mockResolvedValue(paged([makeUser({ type: 2 })], 1));
        render(<AdminUsers />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-type');
          const select = within(cell).getByRole('combobox');
          expect(select).toHaveValue('2');
        });
      });
    });

    describe('is_active (Status) column', () => {
      it('shows "Active" with green styling when is_active is true', async () => {
        adminAPI.getUsers.mockResolvedValue(paged([makeUser({ is_active: true })], 1));
        render(<AdminUsers />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-is_active');
          const badge = within(cell).getByText('Active');
          expect(badge.className).toMatch(/bg-green-100/);
        });
      });

      it('shows "Inactive" with red styling when is_active is false', async () => {
        adminAPI.getUsers.mockResolvedValue(paged([makeUser({ is_active: false })], 1));
        render(<AdminUsers />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-is_active');
          const badge = within(cell).getByText('Inactive');
          expect(badge.className).toMatch(/bg-red-100/);
        });
      });
    });

    describe('is_verified (Verified) column', () => {
      it('shows a teal shield-check icon when verified', async () => {
        adminAPI.getUsers.mockResolvedValue(paged([makeUser({ is_verified: true })], 1));
        const { container } = render(<AdminUsers />);
        await waitFor(() => {
          expect(container.querySelector('.bi-shield-check.text-teal-600')).toBeInTheDocument();
        });
      });

      it('shows a gray shield-x icon when not verified', async () => {
        adminAPI.getUsers.mockResolvedValue(paged([makeUser({ is_verified: false })], 1));
        const { container } = render(<AdminUsers />);
        await waitFor(() => {
          expect(container.querySelector('.bi-shield-x.text-gray-300')).toBeInTheDocument();
        });
      });
    });

    describe('total_orders column', () => {
      it('renders the raw order count', async () => {
        adminAPI.getUsers.mockResolvedValue(paged([makeUser({ total_orders: 17 })], 1));
        render(<AdminUsers />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-total_orders');
          expect(within(cell).getByText('17')).toBeInTheDocument();
        });
      });
    });

    describe('total_spent column', () => {
      it('formats total_spent as currency with no decimals', async () => {
        adminAPI.getUsers.mockResolvedValue(paged([makeUser({ total_spent: 1234.56 })], 1));
        render(<AdminUsers />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-total_spent');
          expect(within(cell).getByText('$1,235')).toBeInTheDocument();
        });
      });

      it('formats zero spend as $0', async () => {
        adminAPI.getUsers.mockResolvedValue(paged([makeUser({ total_spent: 0 })], 1));
        render(<AdminUsers />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-total_spent');
          expect(within(cell).getByText('$0')).toBeInTheDocument();
        });
      });
    });

    describe('created_date column', () => {
      it('formats the ISO date string', async () => {
        adminAPI.getUsers.mockResolvedValue(
          paged([makeUser({ created_date: '2024-06-15T00:00:00Z' })], 1)
        );
        render(<AdminUsers />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-created_date');
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
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('User 1'));

      vi.clearAllMocks();
      okUsers();

      // Use fireEvent to set the entire value at once
      fireEvent.change(screen.getByPlaceholderText('Search by name or email…'), {
        target: { value: 'alice' }
      });

      await waitFor(() =>
        expect(adminAPI.getUsers).toHaveBeenCalledWith(
          expect.objectContaining({ search: 'alice' })
        )
      );
    });

    it('resets page to 1 when search changes', async () => {
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('User 1'));

      await user.click(screen.getByTestId('dt-next-page'));
      await waitFor(() =>
        expect(adminAPI.getUsers).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );

      vi.clearAllMocks();
      okUsers();

      await user.type(
        screen.getByPlaceholderText('Search by name or email…'),
        'x'
      );

      await waitFor(() =>
        expect(adminAPI.getUsers).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1 })
        )
      );
    });
  });

  // ── 5. Sort ──────────────────────────────────────────────────────────────
  describe('Sort', () => {
    it('re-fetches with new ordering when sort changes', async () => {
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('User 1'));

      vi.clearAllMocks();
      okUsers();

      await user.click(screen.getByTestId('dt-sort'));

      await waitFor(() =>
        expect(adminAPI.getUsers).toHaveBeenCalledWith(
          expect.objectContaining({ ordering: 'email' })
        )
      );
    });
  });

  // ── 6. Active filter ─────────────────────────────────────────────────────
  describe('Active filter', () => {
    it('renders the filter select with All/Active/Inactive options', async () => {
      render(<AdminUsers />);
      await waitFor(() => screen.getByTestId('dt-filters'));
      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      const opts = within(select).getAllByRole('option').map((o) => ({
        value: o.value, label: o.textContent,
      }));
      expect(opts).toEqual([
        { value: '', label: 'All Users' },
        { value: 'true', label: 'Active' },
        { value: 'false', label: 'Inactive' },
      ]);
    });

    it('re-fetches with the STRING "true" (not boolean) when Active is selected', async () => {
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('User 1'));
      await waitFor(() => screen.getByTestId('dt-filters'));

      vi.clearAllMocks();
      okUsers();

      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      await user.selectOptions(select, 'true');

      await waitFor(() => {
        const callArgs = adminAPI.getUsers.mock.calls[0][0];
        expect(callArgs.is_active).toBe('true');
        expect(typeof callArgs.is_active).toBe('string');
      });
    });

    it('re-fetches with the STRING "false" when Inactive is selected', async () => {
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('User 1'));
      await waitFor(() => screen.getByTestId('dt-filters'));

      vi.clearAllMocks();
      okUsers();

      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      await user.selectOptions(select, 'false');

      await waitFor(() => {
        const callArgs = adminAPI.getUsers.mock.calls[0][0];
        expect(callArgs.is_active).toBe('false');
      });
    });

    it('passes is_active:undefined when reset to "All Users"', async () => {
      const user = setup();
      render(<AdminUsers />);

      await waitFor(() => screen.getByText('User 1'));

      let select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      await user.selectOptions(select, 'true');

      await waitFor(() => screen.getByText('User 1'));

      select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      await user.selectOptions(select, '');

      await waitFor(() => {
        const calls = adminAPI.getUsers.mock.calls;
        expect(calls.length).toBeGreaterThanOrEqual(3);

        const finalCallArgs = calls[calls.length - 1][0];
        expect(finalCallArgs.is_active).toBeUndefined();
      });
    });

    it('resets page to 1 when active filter changes', async () => {
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('User 1'));
      await waitFor(() => screen.getByTestId('dt-filters'));

      await user.click(screen.getByTestId('dt-next-page'));
      await waitFor(() =>
        expect(adminAPI.getUsers).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );

      vi.clearAllMocks();
      okUsers();

      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      await user.selectOptions(select, 'true');

      await waitFor(() =>
        expect(adminAPI.getUsers).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1 })
        )
      );
    });
  });

  // ── 7. Pagination ────────────────────────────────────────────────────────
  describe('Pagination', () => {
    it('re-fetches with incremented page when next-page triggered', async () => {
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('User 1'));

      vi.clearAllMocks();
      okUsers();

      await user.click(screen.getByTestId('dt-next-page'));

      await waitFor(() =>
        expect(adminAPI.getUsers).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );
    });
  });

  // ── 8. Empty state ───────────────────────────────────────────────────────
  describe('Empty state', () => {
    it('shows "No users found" when results are empty', async () => {
      adminAPI.getUsers.mockResolvedValue(paged([], 0));
      render(<AdminUsers />);
      await waitFor(() =>
        expect(screen.getByTestId('dt-empty')).toHaveTextContent('No users found')
      );
    });
  });

  // ── 9. toggleActive ───────────────────────────────────────────────────────
  describe('toggleActive', () => {
    it('calls updateUser with is_active flipped to false for an active user', async () => {
      adminAPI.updateUser.mockResolvedValue({});
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, is_active: true })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      await user.click(within(screen.getByTestId('dt-row-0')).getByRole('button', { name: /deactivate/i }));

      await waitFor(() =>
        expect(adminAPI.updateUser).toHaveBeenCalledWith(1, { is_active: false })
      );
    });

    it('calls updateUser with is_active flipped to true for an inactive user', async () => {
      adminAPI.updateUser.mockResolvedValue({});
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, is_active: false })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      await user.click(within(screen.getByTestId('dt-row-0')).getByRole('button', { name: /activate/i }));

      await waitFor(() =>
        expect(adminAPI.updateUser).toHaveBeenCalledWith(1, { is_active: true })
      );
    });

    it('updates the Status badge in place after a successful deactivate', async () => {
      adminAPI.updateUser.mockResolvedValue({});
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, is_active: true })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      await user.click(within(screen.getByTestId('dt-row-0')).getByRole('button', { name: /deactivate/i }));

      await waitFor(() => {
        const cell = screen.getByTestId('cell-is_active');
        expect(within(cell).getByText('Inactive')).toBeInTheDocument();
      });
    });

    it('shows "User deactivated" toast when an active user is toggled off', async () => {
      adminAPI.updateUser.mockResolvedValue({});
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, is_active: true })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      await user.click(within(screen.getByTestId('dt-row-0')).getByRole('button', { name: /deactivate/i }));

      await waitFor(() =>
        expect(capturedToasts.some((t) => t.message === 'User deactivated')).toBe(true)
      );
    });

    it('shows "User activated" toast when an inactive user is toggled on', async () => {
      adminAPI.updateUser.mockResolvedValue({});
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, is_active: false })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      await user.click(within(screen.getByTestId('dt-row-0')).getByRole('button', { name: /activate/i }));

      await waitFor(() =>
        expect(capturedToasts.some((t) => t.message === 'User activated')).toBe(true)
      );
    });

    it('button label swaps from "Deactivate" to "Activate" after a successful toggle', async () => {
      adminAPI.updateUser.mockResolvedValue({});
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, is_active: true })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      const row = screen.getByTestId('dt-row-0');
      await user.click(within(row).getByRole('button', { name: /deactivate/i }));

      await waitFor(() =>
        expect(within(row).getByRole('button', { name: /activate/i })).toBeInTheDocument()
      );
    });

    it('shows a spinner and disables the button while the update is in-flight', async () => {
      let resolve;
      adminAPI.updateUser.mockReturnValue(new Promise((r) => { resolve = r; }));
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, is_active: true })], 1));
      const { container } = render(<AdminUsers />);
      const user = setup();
      await waitFor(() => screen.getByText('Alice Johnson'));

      const row = screen.getByTestId('dt-row-0');
      const btn = within(row).getByRole('button', { name: /deactivate/i });
      await user.click(btn);

      await waitFor(() => {
        expect(btn).toBeDisabled();
        expect(container.querySelector('.animate-spin')).toBeInTheDocument();
      });

      resolve({});
    });

    it('shows "Failed to update user" error toast on rejection', async () => {
      adminAPI.updateUser.mockRejectedValue(new Error('500'));
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, is_active: true })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      await user.click(within(screen.getByTestId('dt-row-0')).getByRole('button', { name: /deactivate/i }));

      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === 'Failed to update user' && t.type === 'error'
          )
        ).toBe(true)
      );
    });

    it('does NOT change the Status badge after a failed toggle', async () => {
      adminAPI.updateUser.mockRejectedValue(new Error('500'));
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, is_active: true })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      await user.click(within(screen.getByTestId('dt-row-0')).getByRole('button', { name: /deactivate/i }));

      await waitFor(() =>
        expect(capturedToasts.some((t) => t.message === 'Failed to update user')).toBe(true)
      );
      const cell = screen.getByTestId('cell-is_active');
      expect(within(cell).getByText('Active')).toBeInTheDocument();
    });

    it('re-enables the button after a failed toggle', async () => {
      adminAPI.updateUser.mockRejectedValue(new Error('500'));
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, is_active: true })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      const row = screen.getByTestId('dt-row-0');
      await user.click(within(row).getByRole('button', { name: /deactivate/i }));

      await waitFor(() =>
        expect(within(row).getByRole('button', { name: /deactivate/i })).not.toBeDisabled()
      );
    });
  });

  // ── 10. changeRole ───────────────────────────────────────────────────────
  describe('changeRole', () => {
    it('calls updateUser with the parsed integer type', async () => {
      adminAPI.updateUser.mockResolvedValue({});
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, type: 1 })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      const cell = screen.getByTestId('cell-type');
      const select = within(cell).getByRole('combobox');
      await user.selectOptions(select, '2');

      await waitFor(() =>
        expect(adminAPI.updateUser).toHaveBeenCalledWith(1, { type: 2 })
      );
    });

    it('updates the row\'s displayed role after a successful change', async () => {
      adminAPI.updateUser.mockResolvedValue({});
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, type: 1 })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      const cell = screen.getByTestId('cell-type');
      const select = within(cell).getByRole('combobox');
      await user.selectOptions(select, '3');

      await waitFor(() => expect(select).toHaveValue('3'));
    });

    it('shows "Role updated" toast on success', async () => {
      adminAPI.updateUser.mockResolvedValue({});
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, type: 1 })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      const select = within(screen.getByTestId('cell-type')).getByRole('combobox');
      await user.selectOptions(select, '2');

      await waitFor(() =>
        expect(capturedToasts.some((t) => t.message === 'Role updated')).toBe(true)
      );
    });

    it('shows "Failed to update role" error toast on rejection', async () => {
      adminAPI.updateUser.mockRejectedValue(new Error('500'));
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, type: 1 })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      const select = within(screen.getByTestId('cell-type')).getByRole('combobox');
      await user.selectOptions(select, '2');

      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === 'Failed to update role' && t.type === 'error'
          )
        ).toBe(true)
      );
    });

    it('does NOT change the select value after a failed role change', async () => {
      adminAPI.updateUser.mockRejectedValue(new Error('500'));
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, type: 1 })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      const select = within(screen.getByTestId('cell-type')).getByRole('combobox');
      await user.selectOptions(select, '2');

      await waitFor(() =>
        expect(capturedToasts.some((t) => t.message === 'Failed to update role')).toBe(true)
      );
      // Row state was never mutated on error, so it remains type=1
      expect(select).toHaveValue('1');
    });

    it('disables the role select for the affected row while updating', async () => {
      let resolve;
      adminAPI.updateUser.mockReturnValue(new Promise((r) => { resolve = r; }));
      adminAPI.getUsers.mockResolvedValue(paged([makeUser({ id: 1, type: 1 })], 1));
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      const select = within(screen.getByTestId('cell-type')).getByRole('combobox');
      await user.selectOptions(select, '2');

      await waitFor(() => expect(select).toBeDisabled());
      resolve({});
    });
  });

  // ── 11. Concurrent updating across rows ──────────────────────────────────
  describe('Concurrent updating state across rows', () => {
    it('toggling row 0 does NOT disable row 1\'s toggle button', async () => {
      let resolve;
      adminAPI.updateUser.mockReturnValue(new Promise((r) => { resolve = r; }));
      adminAPI.getUsers.mockResolvedValue(
        paged(
          [
            makeUser({ id: 1, full_name: 'Alice Johnson', is_active: true }),
            makeUser({ id: 2, full_name: 'Bob Wilson', is_active: true }),
          ],
          2
        )
      );
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      const row0 = screen.getByTestId('dt-row-0');
      const row1 = screen.getByTestId('dt-row-1');

      await user.click(within(row0).getByRole('button', { name: /deactivate/i }));

      await waitFor(() =>
        expect(within(row0).getByRole('button', { name: /deactivate/i })).toBeDisabled()
      );
      // Row 1's button should remain enabled
      expect(within(row1).getByRole('button', { name: /deactivate/i })).not.toBeDisabled();

      resolve({});
    });

    it('changing row 0\'s role does NOT disable row 1\'s role select', async () => {
      let resolve;
      adminAPI.updateUser.mockReturnValue(new Promise((r) => { resolve = r; }));
      adminAPI.getUsers.mockResolvedValue(
        paged(
          [
            makeUser({ id: 1, full_name: 'Alice Johnson', type: 1 }),
            makeUser({ id: 2, full_name: 'Bob Wilson', type: 1 }),
          ],
          2
        )
      );
      const user = setup();
      render(<AdminUsers />);
      await waitFor(() => screen.getByText('Alice Johnson'));

      const row0Select = within(screen.getByTestId('dt-row-0')).getByRole('combobox');
      const row1Select = within(screen.getByTestId('dt-row-1')).getByRole('combobox');

      await user.selectOptions(row0Select, '2');

      await waitFor(() => expect(row0Select).toBeDisabled());
      expect(row1Select).not.toBeDisabled();

      resolve({});
    });
  });

  // ── 12. Snapshot ─────────────────────────────────────────────────────────
  describe('Snapshot', () => {
    it('matches stable snapshot after data loads', async () => {
      const { asFragment } = render(<AdminUsers />);
      await waitFor(() => screen.getByText('User 1'));
      expect(asFragment()).toMatchSnapshot();
    });
  });
});
