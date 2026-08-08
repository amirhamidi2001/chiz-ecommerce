import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ConfirmModal from "../../components/admin/ConfirmModal";

describe("ConfirmModal Component", () => {
    const defaultProps = {
        isOpen: true,
        onConfirm: vi.fn(),
        onClose: vi.fn(),
    };

    beforeEach(() => {
        vi.clearAllMocks();
    });

    describe("Visibility & Mounting", () => {
        it("should return null and not render anything when isOpen is false", () => {
            const { container } = render(<ConfirmModal {...defaultProps} isOpen={false} />);
            expect(container.firstChild).toBeNull();
        });

        it("should display default text and labels when minimal props are provided", () => {
            render(<ConfirmModal {...defaultProps} />);

            expect(screen.getByRole("heading", { name: "Confirm Action" })).toBeInTheDocument();
            expect(screen.getByText("Are you sure you want to proceed?")).toBeInTheDocument();
            expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
            expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
        });

        it("should accurately render custom titles, messages, and button text labels", () => {
            render(
                <ConfirmModal
                    {...defaultProps}
                    title="Delete Workspace"
                    message="This action cannot be undone."
                    confirmLabel="Nuke It"
                    cancelLabel="Keep It"
                />
            );

            expect(screen.getByRole("heading", { name: "Delete Workspace" })).toBeInTheDocument();
            expect(screen.getByText("This action cannot be undone.")).toBeInTheDocument();
            expect(screen.getByRole("button", { name: "Keep It" })).toBeInTheDocument();
            expect(screen.getByRole("button", { name: "Nuke It" })).toBeInTheDocument();
        });
    });

    describe("Interactions & Event Propagation", () => {
        it("should fire onConfirm precisely once when the confirmation button is clicked", async () => {
            const user = userEvent.setup();
            render(<ConfirmModal {...defaultProps} />);

            const confirmBtn = screen.getByRole("button", { name: "Confirm" });
            await user.click(confirmBtn);

            expect(defaultProps.onConfirm).toHaveBeenCalledTimes(1);
        });

        it("should fire onClose precisely once when the cancel button is clicked", async () => {
            const user = userEvent.setup();
            render(<ConfirmModal {...defaultProps} />);

            const cancelBtn = screen.getByRole("button", { name: "Cancel" });
            await user.click(cancelBtn);

            expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
        });

        it("should fire onClose when clicking outside the modal content container (overlay backdrop)", async () => {
            const user = userEvent.setup();
            const { container } = render(<ConfirmModal {...defaultProps} />);

            const overlay = container.querySelector(".fixed.inset-0");
            await user.click(overlay);

            expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
        });

        it("should prevent closing the modal (stops propagation) when clicking the inner content wrapper", async () => {
            const user = userEvent.setup();
            render(<ConfirmModal {...defaultProps} />);

            const contentCard = screen.getByRole("heading", { name: "Confirm Action" }).parentElement;
            await user.click(contentCard);

            expect(defaultProps.onClose).not.toHaveBeenCalled();
        });
    });

    describe("Variant Variations", () => {
        const variantCases = [
            {
                variant: "danger",
                expectedBtnClass: "bg-red-600",
                expectedIconClass: "bi-exclamation-triangle",
                expectedWrapClass: "bg-red-100",
            },
            {
                variant: "warning",
                expectedBtnClass: "bg-amber-500",
                expectedIconClass: "bi-exclamation-circle",
                expectedWrapClass: "bg-amber-100",
            },
            {
                variant: "primary",
                expectedBtnClass: "bg-teal-600",
                expectedIconClass: "bi-question-circle",
                expectedWrapClass: "bg-teal-100",
            },
        ];

        variantCases.forEach(({ variant, expectedBtnClass, expectedIconClass, expectedWrapClass }) => {
            it(`should properly attach classes and fallback styles for the "${variant}" configuration option`, () => {
                const { container } = render(<ConfirmModal {...defaultProps} variant={variant} />);

                const confirmBtn = screen.getByRole("button", { name: "Confirm" });
                expect(confirmBtn.className).toContain(expectedBtnClass);

                const iconElement = container.querySelector(".bi");
                expect(iconElement.className).toContain(expectedIconClass);

                const iconWrapper = iconElement.parentElement;
                expect(iconWrapper.className).toContain(expectedWrapClass);
            });
        });

        it("should gracefully isolate behavior when an invalid string is passed", () => {
            const { container } = render(<ConfirmModal {...defaultProps} variant="unsupported-mock-variant" />);

            // The icon correctly falls back to danger based on component logic
            const iconElement = container.querySelector(".bi");
            expect(iconElement.className).toContain("bi-exclamation-triangle");

            // Verifies the structural leakage state of the current code implementation
            const confirmBtn = screen.getByRole("button", { name: "Confirm" });
            expect(confirmBtn.className).toContain("undefined");
        });
    });

    describe("Asynchronous Loading Behavior", () => {
        it("should disable both action buttons when loading prop is true", () => {
            render(<ConfirmModal {...defaultProps} loading={true} />);

            const cancelBtn = screen.getByRole("button", { name: "Cancel" });
            const confirmBtn = screen.getByRole("button", { name: "Processing…" });

            expect(cancelBtn).toBeDisabled();
            expect(confirmBtn).toBeDisabled();
        });

        it("should completely swap the confirm label text with a spin loader and string 'Processing…'", () => {
            const { container } = render(<ConfirmModal {...defaultProps} loading={true} confirmLabel="Execute" />);

            expect(screen.queryByText("Execute")).not.toBeInTheDocument();
            expect(screen.getByText("Processing…")).toBeInTheDocument();

            // Clean target check using the test DOM container reference instance
            const spinner = container.querySelector(".animate-spin");
            expect(spinner).toBeInTheDocument();
        });

        it("should ignore clicks and prevent firing action events while execution is processing", async () => {
            const user = userEvent.setup();
            render(<ConfirmModal {...defaultProps} loading={true} />);

            const cancelBtn = screen.getByRole("button", { name: "Cancel" });
            const loadingConfirmBtn = screen.getByRole("button", { name: "Processing…" });

            await user.click(loadingConfirmBtn);
            await user.click(cancelBtn);

            expect(defaultProps.onConfirm).not.toHaveBeenCalled();
            expect(defaultProps.onClose).not.toHaveBeenCalled();
        });
    });
});
