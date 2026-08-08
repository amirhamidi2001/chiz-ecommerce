import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Cart from '../pages/Cart';

// ─── Module mocks ──────────────────────────────────────────────────────────

vi.mock('../context/CartContext', () => ({
    useCart: vi.fn(),
}));

vi.mock('../services/api', () => ({
    isAuthenticated: vi.fn(),
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
    const actual = await importOriginal();
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

// ─── Imports after mocks ───────────────────────────────────────────────────

import { useCart } from '../context/CartContext';
import { isAuthenticated } from '../services/api';

// ─── Fixtures ──────────────────────────────────────────────────────────────

const makeItem = (overrides = {}) => ({
    id: 1,
    quantity: 2,
    unit_price: '10.00',
    subtotal: '20.00',
    product: {
        name: 'Product 1',
        slug: 'product-1',
        image: '',
        stock: 5,
    },
    ...overrides,
});

const makeCart = (overrides = {}) => ({
    items: [makeItem()],
    subtotal: '20.00',
    total_items: 2,
    ...overrides,
});

const defaultUseCartValue = {
    cart: null,
    loading: false,
    error: null,
    fetchCart: vi.fn(),
    updateItem: vi.fn(),
    removeItem: vi.fn(),
    clearCart: vi.fn(),
};

// ─── Helpers ───────────────────────────────────────────────────────────────

const renderCart = () =>
    render(
        <MemoryRouter>
            <Cart />
        </MemoryRouter>
    );

const setupAuthenticated = (cartOverrides = {}) => {
    isAuthenticated.mockReturnValue(true);
    useCart.mockReturnValue({
        ...defaultUseCartValue,
        cart: makeCart(cartOverrides),
        fetchCart: vi.fn(),
        updateItem: vi.fn().mockResolvedValue({ success: true }),
        removeItem: vi.fn().mockResolvedValue({ success: true }),
        clearCart: vi.fn().mockResolvedValue({ success: true }),
    });
};

// ══════════════════════════════════════════════════════════════════════════════
// Test suite
// ══════════════════════════════════════════════════════════════════════════════

describe('Cart', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        window.confirm = vi.fn(() => true);
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    // ── Auth ─────────────────────────────────────────────────────────────────

    describe('auth', () => {
        it('redirects to /login when the user is not authenticated', () => {
            isAuthenticated.mockReturnValue(false);
            useCart.mockReturnValue({ ...defaultUseCartValue });

            renderCart();

            expect(mockNavigate).toHaveBeenCalledWith('/login');
        });

        it('does not redirect when the user is authenticated', () => {
            setupAuthenticated();

            renderCart();

            expect(mockNavigate).not.toHaveBeenCalled();
        });

        it('calls fetchCart on mount when authenticated', () => {
            const fetchCart = vi.fn();
            isAuthenticated.mockReturnValue(true);
            useCart.mockReturnValue({ ...defaultUseCartValue, fetchCart });

            renderCart();

            expect(fetchCart).toHaveBeenCalledTimes(1);
        });
    });

    // ── Loading ───────────────────────────────────────────────────────────────

    describe('loading', () => {
        it('shows a loading skeleton while cart data is being fetched', () => {
            isAuthenticated.mockReturnValue(true);
            useCart.mockReturnValue({ ...defaultUseCartValue, loading: true });

            renderCart();

            // The CartSkeleton renders 3 animated placeholder rows; we verify the
            // cart item list and empty-state text are absent.
            expect(screen.queryByText('Your cart is empty')).not.toBeInTheDocument();
            expect(screen.queryByText('Product 1')).not.toBeInTheDocument();
        });

        it('does not show item rows or empty state while loading', () => {
            isAuthenticated.mockReturnValue(true);
            useCart.mockReturnValue({
                ...defaultUseCartValue,
                loading: true,
                cart: makeCart(),
            });

            renderCart();

            expect(screen.queryByRole('button', { name: /remove/i })).not.toBeInTheDocument();
        });
    });

    // ── Empty state ───────────────────────────────────────────────────────────

    describe('empty state', () => {
        it('shows the empty cart message when there are no items', () => {
            isAuthenticated.mockReturnValue(true);
            useCart.mockReturnValue({
                ...defaultUseCartValue,
                cart: makeCart({ items: [], total_items: 0, subtotal: '0.00' }),
            });

            renderCart();

            expect(screen.getByText('Your cart is empty')).toBeInTheDocument();
        });

        it('renders a link to continue shopping when the cart is empty', () => {
            isAuthenticated.mockReturnValue(true);
            useCart.mockReturnValue({
                ...defaultUseCartValue,
                cart: makeCart({ items: [], total_items: 0, subtotal: '0.00' }),
            });

            renderCart();

            expect(
                screen.getByRole('link', { name: /continue shopping/i })
            ).toBeInTheDocument();
        });

        it('does not show the order summary when the cart is empty', () => {
            isAuthenticated.mockReturnValue(true);
            useCart.mockReturnValue({
                ...defaultUseCartValue,
                cart: makeCart({ items: [], total_items: 0, subtotal: '0.00' }),
            });

            renderCart();

            expect(screen.queryByText('Order Summary')).not.toBeInTheDocument();
        });
    });

    // ── Cart interactions ─────────────────────────────────────────────────────

    describe('cart interactions', () => {
        describe('rendering', () => {
            it('renders the product name', () => {
                setupAuthenticated();

                renderCart();

                expect(screen.getByText('Product 1')).toBeInTheDocument();
            });

            it('displays the correct unit price', () => {
                setupAuthenticated();

                renderCart();

                expect(screen.getByText('$10.00')).toBeInTheDocument();
            });

            it('displays the line subtotal', () => {
                setupAuthenticated();

                renderCart();

                expect(screen.getAllByText('$20.00').length).toBeGreaterThan(0);
            });

            it('shows the item count in the page heading', () => {
                setupAuthenticated();

                renderCart();

                expect(screen.getByRole('heading', { name: /2 items/i })).toBeInTheDocument();
            });

            it('renders the Order Summary section', () => {
                setupAuthenticated();

                renderCart();

                expect(screen.getByText('Order Summary')).toBeInTheDocument();
            });

            it('renders the Proceed to Checkout link', () => {
                setupAuthenticated();

                renderCart();

                expect(
                    screen.getByRole('link', { name: /proceed to checkout/i })
                ).toBeInTheDocument();
            });
        });

        describe('quantity controls', () => {

            it('calls updateItem with an incremented quantity when + is clicked', async () => {
                const user = userEvent.setup();
                const updateItem = vi.fn().mockResolvedValue({ success: true });
                isAuthenticated.mockReturnValue(true);
                useCart.mockReturnValue({
                    ...defaultUseCartValue,
                    cart: makeCart(),
                    updateItem,
                });

                renderCart();

                // 1. Remove the broken line 269 completely

                // 2. Use the fallback approach that inspects innerHTML for the class icon
                const plusBtn = screen
                    .getAllByRole('button')
                    .find((btn) => btn.innerHTML.includes('bi-plus'));

                // 3. Click the button we safely found
                await user.click(plusBtn);

                expect(updateItem).toHaveBeenCalledWith(1, 3); // quantity 2 → 3
            });

            it('calls updateItem with a decremented quantity when − is clicked', async () => {
                const user = userEvent.setup();
                const updateItem = vi.fn().mockResolvedValue({ success: true });
                isAuthenticated.mockReturnValue(true);
                useCart.mockReturnValue({
                    ...defaultUseCartValue,
                    cart: makeCart(),
                    updateItem,
                });

                renderCart();

                const minusBtn = screen
                    .getAllByRole('button')
                    .find((btn) => btn.innerHTML.includes('bi-dash'));

                await user.click(minusBtn);

                expect(updateItem).toHaveBeenCalledWith(1, 1); // quantity 2 → 1
            });

            it('disables the − button when quantity is 1', () => {
                isAuthenticated.mockReturnValue(true);
                useCart.mockReturnValue({
                    ...defaultUseCartValue,
                    cart: makeCart({
                        items: [makeItem({ quantity: 1, subtotal: '10.00' })],
                        subtotal: '10.00',
                        total_items: 1,
                    }),
                });

                renderCart();

                const minusBtn = screen
                    .getAllByRole('button')
                    .find((btn) => btn.innerHTML.includes('bi-dash'));

                expect(minusBtn).toBeDisabled();
            });

            it('shows an error toast when updateItem fails', async () => {
                const user = userEvent.setup();
                isAuthenticated.mockReturnValue(true);
                useCart.mockReturnValue({
                    ...defaultUseCartValue,
                    cart: makeCart(),
                    updateItem: vi.fn().mockResolvedValue({ success: false, message: 'Update failed' }),
                });

                renderCart();

                const plusBtn = screen
                    .getAllByRole('button')
                    .find((btn) => btn.innerHTML.includes('bi-plus'));

                await user.click(plusBtn);

                expect(await screen.findByText('Update failed')).toBeInTheDocument();
            });
        });

        describe('remove item', () => {
            it('calls removeItem with the correct item id when Remove is clicked', async () => {
                const user = userEvent.setup();
                const removeItem = vi.fn().mockResolvedValue({ success: true });
                isAuthenticated.mockReturnValue(true);
                useCart.mockReturnValue({
                    ...defaultUseCartValue,
                    cart: makeCart(),
                    removeItem,
                });

                renderCart();

                await user.click(screen.getByRole('button', { name: /remove/i }));

                expect(removeItem).toHaveBeenCalledWith(1);
            });

            it('shows a success toast after removing an item', async () => {
                const user = userEvent.setup();
                isAuthenticated.mockReturnValue(true);
                useCart.mockReturnValue({
                    ...defaultUseCartValue,
                    cart: makeCart(),
                    removeItem: vi.fn().mockResolvedValue({ success: true }),
                });

                renderCart();

                await user.click(screen.getByRole('button', { name: /remove/i }));

                expect(
                    await screen.findByText('Item removed from cart.')
                ).toBeInTheDocument();
            });

            it('shows an error toast when removal fails', async () => {
                const user = userEvent.setup();
                isAuthenticated.mockReturnValue(true);
                useCart.mockReturnValue({
                    ...defaultUseCartValue,
                    cart: makeCart(),
                    removeItem: vi.fn().mockResolvedValue({ success: false, message: 'Remove failed' }),
                });

                renderCart();

                await user.click(screen.getByRole('button', { name: /remove/i }));

                expect(await screen.findByText('Remove failed')).toBeInTheDocument();
            });
        });

        describe('clear cart', () => {
            it('shows the browser confirm dialog when Clear Cart is clicked', async () => {
                const user = userEvent.setup();
                setupAuthenticated();

                renderCart();

                await user.click(screen.getByRole('button', { name: /clear cart/i }));

                expect(window.confirm).toHaveBeenCalledWith(
                    'Are you sure you want to clear your entire cart?'
                );
            });

            it('calls clearCart when the user confirms the dialog', async () => {
                const user = userEvent.setup();
                const clearCart = vi.fn().mockResolvedValue({ success: true });
                window.confirm = vi.fn(() => true);
                isAuthenticated.mockReturnValue(true);
                useCart.mockReturnValue({ ...defaultUseCartValue, cart: makeCart(), clearCart });

                renderCart();

                await user.click(screen.getByRole('button', { name: /clear cart/i }));

                expect(clearCart).toHaveBeenCalledTimes(1);
            });

            it('does not call clearCart when the user cancels the dialog', async () => {
                const user = userEvent.setup();
                const clearCart = vi.fn();
                window.confirm = vi.fn(() => false);
                isAuthenticated.mockReturnValue(true);
                useCart.mockReturnValue({ ...defaultUseCartValue, cart: makeCart(), clearCart });

                renderCart();

                await user.click(screen.getByRole('button', { name: /clear cart/i }));

                expect(clearCart).not.toHaveBeenCalled();
            });

            it('shows a success toast after clearing the cart', async () => {
                const user = userEvent.setup();
                window.confirm = vi.fn(() => true);
                isAuthenticated.mockReturnValue(true);
                useCart.mockReturnValue({
                    ...defaultUseCartValue,
                    cart: makeCart(),
                    clearCart: vi.fn().mockResolvedValue({ success: true }),
                });

                renderCart();

                await user.click(screen.getByRole('button', { name: /clear cart/i }));

                expect(await screen.findByText('Cart cleared.')).toBeInTheDocument();
            });

            it('shows an error toast when clearing the cart fails', async () => {
                const user = userEvent.setup();
                window.confirm = vi.fn(() => true);
                isAuthenticated.mockReturnValue(true);
                useCart.mockReturnValue({
                    ...defaultUseCartValue,
                    cart: makeCart(),
                    clearCart: vi.fn().mockResolvedValue({ success: false, message: 'Clear failed' }),
                });

                renderCart();

                await user.click(screen.getByRole('button', { name: /clear cart/i }));

                expect(await screen.findByText('Clear failed')).toBeInTheDocument();
            });
        });
    });

    // ── Coupon ────────────────────────────────────────────────────────────────

    describe('coupon', () => {
        it('applies a $20 discount for the valid coupon DISCOUNT20', async () => {
            const user = userEvent.setup();
            setupAuthenticated({ subtotal: '100.00', total_items: 1 });

            renderCart();

            await user.type(screen.getByPlaceholderText(/coupon code/i), 'DISCOUNT20');
            await user.click(screen.getByRole('button', { name: /apply coupon/i }));

            expect(await screen.findByText(/coupon applied/i)).toBeInTheDocument();
            expect(screen.getByText('-$20.00')).toBeInTheDocument();
        });

        it('shows a success toast when a valid coupon is applied', async () => {
            const user = userEvent.setup();
            setupAuthenticated({ subtotal: '100.00', total_items: 1 });

            renderCart();

            await user.type(screen.getByPlaceholderText(/coupon code/i), 'DISCOUNT20');
            await user.click(screen.getByRole('button', { name: /apply coupon/i }));

            expect(
                await screen.findByText('Coupon applied! $20 discount added.')
            ).toBeInTheDocument();
        });

        it('shows an error toast for an invalid coupon code', async () => {
            const user = userEvent.setup();
            setupAuthenticated();

            renderCart();

            await user.type(screen.getByPlaceholderText(/coupon code/i), 'BADCODE');
            await user.click(screen.getByRole('button', { name: /apply coupon/i }));

            expect(await screen.findByText('Invalid coupon code.')).toBeInTheDocument();
        });

        it('does not apply a discount for an invalid coupon code', async () => {
            const user = userEvent.setup();
            setupAuthenticated();

            renderCart();

            await user.type(screen.getByPlaceholderText(/coupon code/i), 'BADCODE');
            await user.click(screen.getByRole('button', { name: /apply coupon/i }));

            await waitFor(() => {
                expect(screen.queryByText(/-\$20\.00/)).not.toBeInTheDocument();
            });
        });

        it('disables the coupon button after successful application instead of allowing a second click', async () => {
            const user = userEvent.setup();
            setupAuthenticated({ subtotal: '100.00', total_items: 1 });

            renderCart();

            // Apply once
            await user.type(screen.getByPlaceholderText(/coupon code/i), 'DISCOUNT20');
            await user.click(screen.getByRole('button', { name: /apply coupon/i }));
            await screen.findByText('Coupon applied! $20 discount added.');

            // Assert it is disabled so it can't be clicked again
            expect(screen.getByRole('button', { name: /applied/i })).toBeDisabled();
        });

        it('disables the coupon input and button after successful application', async () => {
            const user = userEvent.setup();
            setupAuthenticated({ subtotal: '100.00', total_items: 1 });

            renderCart();

            await user.type(screen.getByPlaceholderText(/coupon code/i), 'DISCOUNT20');
            await user.click(screen.getByRole('button', { name: /apply coupon/i }));
            await screen.findByText('Coupon applied! $20 discount added.');

            expect(screen.getByPlaceholderText(/coupon code/i)).toBeDisabled();
            expect(screen.getByRole('button', { name: /applied/i })).toBeDisabled();
        });
    });

    // ── Shipping ──────────────────────────────────────────────────────────────

    describe('shipping', () => {
        it('defaults to Standard Delivery ($4.99)', () => {
            setupAuthenticated({ subtotal: '20.00', total_items: 1 });

            renderCart();

            expect(screen.getByRole('radio', { name: /standard delivery/i })).toBeChecked();
        });

        it('updates the selected shipping method when Express Delivery is chosen', async () => {
            const user = userEvent.setup();
            setupAuthenticated({ subtotal: '20.00', total_items: 1 });

            renderCart();

            await user.click(screen.getByRole('radio', { name: /express delivery/i }));

            expect(screen.getByRole('radio', { name: /express delivery/i })).toBeChecked();
            expect(screen.getByRole('radio', { name: /standard delivery/i })).not.toBeChecked();
        });

        it('reflects the Express Delivery cost ($12.99) in the order total', async () => {
            const user = userEvent.setup();
            // subtotal=20, tax=2, express=12.99 → total=34.99
            setupAuthenticated({ subtotal: '20.00', total_items: 1 });

            renderCart();

            await user.click(screen.getByRole('radio', { name: /express delivery/i }));

            expect(screen.getByText('$34.99')).toBeInTheDocument();
        });

        it('disables Free Shipping when the order subtotal is below $300', () => {
            setupAuthenticated({ subtotal: '20.00', total_items: 1 });

            renderCart();

            expect(screen.getByRole('radio', { name: /free shipping/i })).toBeDisabled();
        });

        it('enables Free Shipping when the order subtotal meets the $300 threshold', () => {
            setupAuthenticated({ subtotal: '300.00', total_items: 30 });

            renderCart();

            expect(screen.getByRole('radio', { name: /free shipping/i })).not.toBeDisabled();
        });
    });

    // ── Error handling ────────────────────────────────────────────────────────

    describe('error handling', () => {
        it('shows an API error banner when the error state is set', () => {
            isAuthenticated.mockReturnValue(true);
            useCart.mockReturnValue({
                ...defaultUseCartValue,
                error: 'Failed to load cart',
                cart: null,
            });

            renderCart();

            expect(screen.getByText(/failed to load cart/i)).toBeInTheDocument();
        });

        it('renders a Retry button inside the error banner', () => {
            isAuthenticated.mockReturnValue(true);
            useCart.mockReturnValue({
                ...defaultUseCartValue,
                error: 'Network error',
                cart: null,
            });

            renderCart();

            expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
        });

        it('calls fetchCart when the Retry button is clicked', async () => {
            const user = userEvent.setup();
            const fetchCart = vi.fn();
            isAuthenticated.mockReturnValue(true);
            useCart.mockReturnValue({
                ...defaultUseCartValue,
                error: 'Network error',
                cart: null,
                fetchCart,
            });

            renderCart();

            await user.click(screen.getByRole('button', { name: /retry/i }));

            // fetchCart is called once on mount, and once on retry
            expect(fetchCart).toHaveBeenCalledTimes(2);
        });

        it('does not show the error banner when there is no error', () => {
            setupAuthenticated();

            renderCart();

            // No generic error message visible
            expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
        });
    });
});