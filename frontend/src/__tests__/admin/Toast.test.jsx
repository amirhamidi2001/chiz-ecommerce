import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import Toast, { useToast } from "../../components/admin/Toast";

describe("Toast Component & useToast Hook", () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.runOnlyPendingTimers();
        vi.useRealTimers();
    });

    describe("Unit Tests: Component Rendering", () => {
        it("should render nothing when toast prop is null", () => {
            const { container } = render(<Toast toast={null} onDismiss={vi.fn()} />);
            expect(container.firstChild).toBeNull();
        });

        it("should render toast message correctly", () => {
            const toastData = { msg: "Operation Successful", type: "success" };
            render(<Toast toast={toastData} onDismiss={vi.fn()} />);

            expect(screen.getByText("Operation Successful")).toBeInTheDocument();
        });

        const styleMatrix = [
            { type: "success", bgClass: "bg-teal-600", iconClass: "bi-check-circle" },
            { type: "error", bgClass: "bg-red-500", iconClass: "bi-x-circle" },
            { type: "warning", bgClass: "bg-amber-500", iconClass: "bi-exclamation-triangle" },
            { type: "info", bgClass: "bg-blue-500", iconClass: "bi-info-circle" },
        ];

        styleMatrix.forEach(({ type, bgClass, iconClass }) => {
            it(`should render correct styling and iconography for type: "${type}"`, () => {
                const toastData = { msg: `${type} alert`, type };
                const { container } = render(<Toast toast={toastData} onDismiss={vi.fn()} />);

                const mainContainer = container.querySelector(".fixed");
                const iconElement = container.querySelector(".bi");

                expect(mainContainer).toHaveClass(bgClass);
                expect(iconElement).toHaveClass(iconClass);
            });
        });

        it("should fallback to success styles and icons if given an unknown type", () => {
            const toastData = { msg: "Unknown message mapping", type: "critical-error-fallback" };
            const { container } = render(<Toast toast={toastData} onDismiss={vi.fn()} />);

            const mainContainer = container.querySelector(".fixed");
            const iconElement = container.querySelector(".bi");

            expect(mainContainer).toHaveClass("bg-teal-600");
            expect(iconElement).toHaveClass("bi-check-circle");
        });
    });

    describe("Integration Tests: Lifecycle & Animation Timers", () => {
        it("should apply visibility animation classes upon mounting", () => {
            const toastData = { msg: "Animating In", type: "info" };
            const { container } = render(<Toast toast={toastData} onDismiss={vi.fn()} />);
            const mainContainer = container.querySelector(".fixed");

            expect(mainContainer).toHaveClass("opacity-100", "translate-y-0");
            expect(mainContainer).not.toHaveClass("opacity-0", "-translate-y-2");
        });

        it("should trigger onDismiss precisely after the execution duration plus transition delay", () => {
            const onDismissMock = vi.fn();
            const duration = 2000;
            const toastData = { msg: "Timed Component", type: "success" };

            render(<Toast toast={toastData} onDismiss={onDismissMock} duration={duration} />);

            // Step forward right before the core duration completes
            act(() => {
                vi.advanceTimersByTime(duration - 1);
            });
            expect(onDismissMock).not.toHaveBeenCalled();

            // Complete the main duration timeout
            act(() => {
                vi.advanceTimersByTime(1);
            });
            expect(onDismissMock).not.toHaveBeenCalled();

            // Step forward the 300ms needed to clear the exit animation timeout
            act(() => {
                vi.advanceTimersByTime(300);
            });
            expect(onDismissMock).toHaveBeenCalledTimes(1);
        });

        it("should trigger immediate exit animation changes and delayed dismissal on manual close interaction", () => {
            const onDismissMock = vi.fn();
            const toastData = { msg: "Manual Intercept Toast", type: "warning" };

            const { container } = render(<Toast toast={toastData} onDismiss={onDismissMock} />);
            const mainContainer = container.querySelector(".fixed");
            const closeButton = screen.getByRole("button");

            expect(mainContainer).toHaveClass("opacity-100");

            // Use fireEvent to trigger synchronous click without timer side-effects
            fireEvent.click(closeButton);

            // Animation classes should toggle to un-mounted state instantly 
            expect(mainContainer).toHaveClass("opacity-0", "-translate-y-2");
            expect(onDismissMock).not.toHaveBeenCalled();

            // Wait out the 300ms cleanup transition delay
            act(() => {
                vi.advanceTimersByTime(300);
            });
            expect(onDismissMock).toHaveBeenCalledTimes(1);
        });
    });

    describe("Unit Tests: useToast Custom Hook", () => {
        const HookTesterComponent = () => {
            const { toast, show, dismiss } = useToast();
            return (
                <div>
                    <div data-testid="toast-state">{JSON.stringify(toast)}</div>
                    <button data-testid="show-btn" onClick={() => show("Hello Context", "info")}>Show</button>
                    <button data-testid="dismiss-btn" onClick={dismiss}>Dismiss</button>
                </div>
            );
        };

        it("should initialize with state set to null", () => {
            render(<HookTesterComponent />);
            expect(screen.getByTestId("toast-state").textContent).toBe("null");
        });

        it("should populate active toast data values when executing show()", () => {
            render(<HookTesterComponent />);

            fireEvent.click(screen.getByTestId("show-btn"));

            const activeState = JSON.parse(screen.getByTestId("toast-state").textContent);
            expect(activeState).toEqual({ msg: "Hello Context", type: "info" });
        });

        it("should drop back to null state values immediately when executing dismiss()", () => {
            render(<HookTesterComponent />);

            // Open first
            fireEvent.click(screen.getByTestId("show-btn"));
            expect(screen.getByTestId("toast-state").textContent).not.toBe("null");

            // Terminate state manually
            fireEvent.click(screen.getByTestId("dismiss-btn"));
            expect(screen.getByTestId("toast-state").textContent).toBe("null");
        });
    });
});
