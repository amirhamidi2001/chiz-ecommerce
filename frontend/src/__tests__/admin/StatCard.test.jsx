import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import StatCard from "../../components/admin/StatCard";

describe("StatCard Component", () => {
    const defaultProps = {
        title: "Total Revenue",
        value: "12450",
        prefix: "$",
        suffix: " USD",
    };

    // --- 1. RENDER & CONTENT TESTS ---
    describe("Rendering & Formatting", () => {
        it("renders title, formatted value with prefix and suffix correctly", () => {
            render(<StatCard {...defaultProps} />);

            expect(screen.getByText("Total Revenue")).toBeInTheDocument();
            expect(screen.getByText("$12450 USD")).toBeInTheDocument();
        });

        it("handles numeric values cleanly without throwing type errors", () => {
            render(<StatCard title="Active Users" value={5420} />);
            expect(screen.getByText("5420")).toBeInTheDocument();
        });

        it("renders default icon if none is provided", () => {
            const { container } = render(<StatCard {...defaultProps} />);
            const iconEl = container.querySelector(".bi");
            expect(iconEl).toHaveClass("bi-graph-up");
        });

        it("renders custom Bootstrap icon when passed down", () => {
            const { container } = render(<StatCard {...defaultProps} icon="bi-cart" />);
            const iconEl = container.querySelector(".bi");
            expect(iconEl).toHaveClass("bi-cart");
        });
    });

    // --- 2. TREND & PERCENTAGE CHANGE TESTS ---
    describe("Trend Indicators (change prop)", () => {
        it("renders positive change indicators cleanly", () => {
            const { container } = render(<StatCard {...defaultProps} change={12.5} />);

            expect(screen.getByText("12.5%")).toBeInTheDocument();
            expect(screen.getByText("Up 12.5% vs last period")).toBeInTheDocument();

            const badge = screen.getByText("12.5%");
            expect(badge).toHaveClass("bg-green-100", "text-green-700");

            const trendIcon = container.querySelector(".bi-arrow-up-short");
            expect(trendIcon).toBeInTheDocument();
        });

        it("renders negative change indicators cleanly", () => {
            const { container } = render(<StatCard {...defaultProps} change={-5.2} />);

            // Math.abs should drop the negative sign in the visual presentation
            expect(screen.getByText("5.2%")).toBeInTheDocument();
            expect(screen.getByText("Down 5.2% vs last period")).toBeInTheDocument();

            const badge = screen.getByText("5.2%");
            expect(badge).toHaveClass("bg-red-100", "text-red-700");

            const trendIcon = container.querySelector(".bi-arrow-down-short");
            expect(trendIcon).toBeInTheDocument();
        });

        it("renders flat / zero change indicators correctly", () => {
            const { container } = render(<StatCard {...defaultProps} change={0} />);

            expect(screen.getByText("0%")).toBeInTheDocument();
            expect(screen.getByText("No change vs last period")).toBeInTheDocument();

            const badge = screen.getByText("0%");
            expect(badge).toHaveClass("bg-gray-100", "text-gray-500");

            const trendIcon = container.querySelector(".bi-dash");
            expect(trendIcon).toBeInTheDocument();
        });

        it("completely omits trend elements when change is null", () => {
            render(<StatCard {...defaultProps} change={null} />);

            expect(screen.queryByText(/vs last period/i)).not.toBeInTheDocument();
            expect(screen.queryByText("%")).not.toBeInTheDocument();
        });
    });

    // --- 3. THEME PALETTE HANDLING ---
    describe("Color Palettes", () => {
        it("applies the specified color design token mapping", () => {
            const { container } = render(<StatCard {...defaultProps} color="amber" />);
            const iconWrapper = container.querySelector(".w-11.h-11");
            const icon = container.querySelector(".bi");

            expect(iconWrapper).toHaveClass("bg-amber-50");
            expect(icon).toHaveClass("text-amber-600");
        });

        it("gracefully falls back to teal when an invalid color is targeted", () => {
            const { container } = render(<StatCard {...defaultProps} color="invalid-color" />);
            const iconWrapper = container.querySelector(".w-11.h-11");
            const icon = container.querySelector(".bi");

            expect(iconWrapper).toHaveClass("bg-teal-50");
            expect(icon).toHaveClass("text-teal-600");
        });
    });

    // --- 4. LOADING STATE MOCKING ---
    describe("Loading Skeleton State", () => {
        it("renders placeholder items and hides active content blocks during load states", () => {
            const { container } = render(<StatCard {...defaultProps} change={15} loading={true} />);

            // Skeletons must present pulse animation tokens
            const pulseElements = container.querySelectorAll(".animate-pulse");
            expect(pulseElements.length).toBeGreaterThan(0);

            // Raw metrics should be structuralized out of standard visibility paths
            expect(screen.queryByText("$12450 USD")).not.toBeInTheDocument();
            expect(screen.queryByText("Total Revenue")).not.toBeInTheDocument();
            expect(screen.queryByText("15%")).not.toBeInTheDocument();
        });
    });

    // --- 5. INTERACTION & INTERFACE DECORATORS ---
    describe("Interactions & Event Hooks", () => {
        it("fires onClick event successfully and handles style changes when actionable", () => {
            const handleClick = vi.fn();
            const { container } = render(<StatCard {...defaultProps} onClick={handleClick} />);

            const wrapperCard = container.firstChild;
            expect(wrapperCard).toHaveClass("cursor-pointer", "hover:shadow-md", "transition");

            fireEvent.click(wrapperCard);
            expect(handleClick).toHaveBeenCalledTimes(1);
        });

        it("does not apply clickable styling flags if onClick prop is undefined", () => {
            const { container } = render(<StatCard {...defaultProps} onClick={undefined} />);
            const wrapperCard = container.firstChild;

            expect(wrapperCard).not.toHaveClass("cursor-pointer");
            expect(wrapperCard).not.toHaveClass("hover:shadow-md");
        });
    });
});
