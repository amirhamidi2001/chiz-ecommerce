import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DataTable from "../../components/admin/DataTable";

describe("DataTable Component", () => {
    const mockColumns = [
        { key: "id", label: "ID", sortable: false },
        { key: "name", label: "Name", sortable: true, className: "custom-name-col" },
        { key: "role", label: "Role", sortable: true },
        {
            key: "status",
            label: "Status",
            sortable: false,
            render: (val) => <span className="status-badge">{val.toUpperCase()}</span>
        }
    ];

    const mockData = [
        { id: 1, name: "Alice Johnson", role: "Admin", status: "active" },
        { id: 2, name: "Bob Smith", role: "Editor", status: "inactive" },
        { id: 3, name: "Charlie Brown", role: "Viewer", status: "active" }
    ];

    const defaultProps = {
        columns: mockColumns,
        data: mockData,
        loading: false,
        totalCount: 3,
        page: 1,
        pageSize: 10,
        onPageChange: vi.fn(),
        sort: "",
        onSort: vi.fn(),
        onSearch: vi.fn(),
        search: ""
    };

    beforeEach(() => {
        vi.resetAllMocks();
    });

    // ── RENDER STATES ──────────────────────────────────────────────────────────
    describe("Rendering & Structural Variants", () => {
        it("renders table headers, custom classNames, and accurate result counts", () => {
            render(<DataTable {...defaultProps} />);

            expect(screen.getByText("3 results")).toBeInTheDocument();
            expect(screen.getByRole("columnheader", { name: /id/i })).toBeInTheDocument();

            const nameHeader = screen.getByRole("columnheader", { name: /name/i });
            expect(nameHeader).toBeInTheDocument();
            expect(nameHeader).toHaveClass("custom-name-col");
        });

        it("renders rows and formatted text matching data structures", () => {
            // Destructure container from render to use standard DOM selectors
            const { container } = render(<DataTable {...defaultProps} />);

            expect(screen.getByText("Alice Johnson")).toBeInTheDocument();
            expect(screen.getByText("Bob Smith")).toBeInTheDocument();

            // Asserts custom cell renderer execution via standard class selector
            const statusBadges = container.querySelectorAll(".status-badge");
            expect(statusBadges).toHaveLength(3);
            expect(statusBadges[0]).toHaveTextContent("ACTIVE");
        });

        it("displays a placeholder dash '—' when data fields are null or undefined", () => {
            const incompleteData = [{ id: 1, name: "Incomplete User", role: null, status: "active" }];
            render(<DataTable {...defaultProps} data={incompleteData} totalCount={1} />);

            expect(screen.getByText("—")).toBeInTheDocument();
        });

        it("renders loading skeletons and ignores empty states when loading is true", () => {
            render(<DataTable {...defaultProps} data={[]} totalCount={0} loading={true} />);

            // Under loading state, 5 structural skeleton rows are drawn
            const rows = screen.getAllByRole("row");
            // 1 header row + 5 skeleton rows = 6 total rows
            expect(rows).toHaveLength(6);
            expect(screen.queryByText("No records found")).not.toBeInTheDocument();
        });

        it("displays configurable empty view states when dataset is empty", () => {
            render(
                <DataTable
                    {...defaultProps}
                    data={[]}
                    totalCount={0}
                    emptyIcon="bi-custom-icon"
                    emptyText="Custom Empty Notice"
                />
            );

            expect(screen.getByText("Custom Empty Notice")).toBeInTheDocument();
            const icon = screen.getByRole("cell").querySelector("i");
            expect(icon).toHaveClass("bi-custom-icon");
        });

        it("injects custom actions column when rowActions generator prop is supplied", () => {
            const mockRowActions = (row) => <button>Delete {row.name}</button>;
            render(<DataTable {...defaultProps} rowActions={mockRowActions} />);

            expect(screen.getByRole("columnheader", { name: /actions/i })).toBeInTheDocument();
            expect(screen.getByRole("button", { name: /delete alice johnson/i })).toBeInTheDocument();
        });

        it("injects additional declarative filter node controls into the toolbar layout", () => {
            const filterWidget = <select data-testid="status-filter"><option>All</option></select>;
            render(<DataTable {...defaultProps} filters={filterWidget} />);

            expect(screen.getByTestId("status-filter")).toBeInTheDocument();
        });
    });

    // ── DEBOUNCED SEARCH TRGGERING ─────────────────────────────────────────────
    describe("Search Input Interactions", () => {
        beforeEach(() => {
            vi.useFakeTimers();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        it("debounces execution over 380ms window and resets current page context", async () => {
            render(<DataTable {...defaultProps} />);
            const searchInput = screen.getByPlaceholderText("Search…");

            // Simulate character sequences
            fireEvent.change(searchInput, { target: { value: "A" } });
            fireEvent.change(searchInput, { target: { value: "Al" } });
            fireEvent.change(searchInput, { target: { value: "Ali" } });

            // Action should not trigger instantly
            expect(defaultProps.onSearch).not.toHaveBeenCalled();

            // Forward clocks right before the execution milestone (380ms)
            vi.advanceTimersByTime(379);
            expect(defaultProps.onSearch).not.toHaveBeenCalled();

            // Advance past threshold limit
            vi.advanceTimersByTime(1);
            expect(defaultProps.onSearch).toHaveBeenCalledTimes(1);
            expect(defaultProps.onSearch).toHaveBeenCalledWith("Ali");
            expect(defaultProps.onPageChange).toHaveBeenCalledWith(1);
        });

        it("omits search element render if onSearch routine property is omitted", () => {
            render(<DataTable {...defaultProps} onSearch={undefined} />);
            expect(screen.queryByPlaceholderText("Search…")).not.toBeInTheDocument();
        });
    });

    // ── SORTING ALGORITHMS ─────────────────────────────────────────────────────
    describe("Column Sorting Matrix Actions", () => {
        it("cycles through strict sort token prefixes across clicks on sortable headers", () => {
            const { rerender } = render(<DataTable {...defaultProps} sort="" />);
            const nameHeader = screen.getByRole("columnheader", { name: /name/i });

            // State 1: Sort is empty string -> clicking sets descending sort prefix '-'
            fireEvent.click(nameHeader);
            expect(defaultProps.onSort).toHaveBeenLastCalledWith("-name");

            // State 2: Sort is currently descending -> clicking flips to ascending order
            rerender(<DataTable {...defaultProps} sort="-name" />);
            fireEvent.click(nameHeader);
            expect(defaultProps.onSort).toHaveBeenLastCalledWith("name");

            // State 3: Sort is currently ascending -> clicking flips back to descending order
            rerender(<DataTable {...defaultProps} sort="name" />);
            fireEvent.click(nameHeader);
            expect(defaultProps.onSort).toHaveBeenLastCalledWith("-name");
        });

        it("suppresses sorting handlers and execution on nonsortable columns", () => {
            render(<DataTable {...defaultProps} />);
            const idHeader = screen.getByRole("columnheader", { name: /id/i });

            fireEvent.click(idHeader);
            expect(defaultProps.onSort).not.toHaveBeenCalled();
        });

        it("renders precise CSS bootstrap icon nodes indicating active order directions", () => {
            const { rerender } = render(<DataTable {...defaultProps} sort="name" />);

            // Ascending active indicator
            let sortIcon = screen.getByRole("columnheader", { name: /name/i }).querySelector("i");
            expect(sortIcon).toHaveClass("bi-sort-up");

            // Descending active indicator
            rerender(<DataTable {...defaultProps} sort="-name" />);
            sortIcon = screen.getByRole("columnheader", { name: /name/i }).querySelector("i");
            expect(sortIcon).toHaveClass("bi-sort-down");

            // Default dual arrow indicators on idle columns
            const unsortedIcon = screen.getByRole("columnheader", { name: /role/i }).querySelector("i");
            expect(unsortedIcon).toHaveClass("bi-arrow-down-up");
        });
    });

    // ── PAGINATION MATRIX ──────────────────────────────────────────────────────
    describe("Pagination Engine Logic", () => {
        it("hides pagination controls if total dataset yields single page boundaries", () => {
            render(<DataTable {...defaultProps} totalCount={5} pageSize={10} page={1} />);
            expect(screen.queryByText(/page 1 of/i)).not.toBeInTheDocument();
        });

        it("disables first/prev boundaries on first page and last/next buttons on last page", () => {
            const { rerender } = render(<DataTable {...defaultProps} totalCount={30} pageSize={10} page={1} />);

            const firstBtn = screen.getByRole("button", { name: "«" });
            const prevBtn = screen.getByRole("button", { name: "‹" });
            const nextBtn = screen.getByRole("button", { name: "›" });
            const lastBtn = screen.getByRole("button", { name: "»" });

            expect(firstBtn).toBeDisabled();
            expect(prevBtn).toBeDisabled();
            expect(nextBtn).toBeEnabled();
            expect(lastBtn).toBeEnabled();

            // Shift perspective to the final page boundaries
            rerender(<DataTable {...defaultProps} totalCount={30} pageSize={10} page={3} />);

            expect(firstBtn).toBeEnabled();
            expect(prevBtn).toBeEnabled();
            expect(nextBtn).toBeDisabled();
            expect(lastBtn).toBeDisabled();
        });

        it("triggers explicit onPageChange signals across standard navigation buttons", () => {
            render(<DataTable {...defaultProps} totalCount={30} pageSize={10} page={2} />);

            fireEvent.click(screen.getByRole("button", { name: "«" }));
            expect(defaultProps.onPageChange).toHaveBeenLastCalledWith(1);

            fireEvent.click(screen.getByRole("button", { name: "‹" }));
            expect(defaultProps.onPageChange).toHaveBeenLastCalledWith(1);

            fireEvent.click(screen.getByRole("button", { name: "›" }));
            expect(defaultProps.onPageChange).toHaveBeenLastCalledWith(3);

            fireEvent.click(screen.getByRole("button", { name: "»" }));
            expect(defaultProps.onPageChange).toHaveBeenLastCalledWith(3);
        });

        it("formats page navigation lists using ellipses ('…') when pages scale up highly", () => {
            // Setup scenarios for 10 structural pages, active inside page 5
            render(<DataTable {...defaultProps} totalCount={100} pageSize={10} page={5} />);

            // Expectation configuration: Always show First (1), Last (10), and neighbors to current page (4, 5, 6)
            // Array calculation splits at gaps: [1, "…", 4, 5, 6, "…", 10]
            expect(screen.getByRole("button", { name: "1" })).toBeInTheDocument();
            expect(screen.getByRole("button", { name: "4" })).toBeInTheDocument();
            expect(screen.getByRole("button", { name: "5" })).toBeInTheDocument();
            expect(screen.getByRole("button", { name: "6" })).toBeInTheDocument();
            expect(screen.getByRole("button", { name: "10" })).toBeInTheDocument();

            const ellipses = screen.getAllByText("…");
            expect(ellipses).toHaveLength(2);
        });

        it("routes updates cleanly to the targeted page when individual specific numeric triggers are clicked", () => {
            render(<DataTable {...defaultProps} totalCount={30} pageSize={10} page={1} />);

            const pageThreeBtn = screen.getByRole("button", { name: "3" });
            fireEvent.click(pageThreeBtn);

            expect(defaultProps.onPageChange).toHaveBeenCalledWith(3);
        });
    });
});
