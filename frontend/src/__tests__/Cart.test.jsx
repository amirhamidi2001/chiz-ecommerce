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
    applyCoupon: vi.fn(),
    removeCoupon: vi.fn(),
};

// ─── Helpers ───────────────────────────────────────────────────────────────

const renderCart = () =>
    render(
        <MemoryRouter>
            <Cart />
        </MemoryRouter>
    );

const setupAuthenticated = (cartOverrides = {}, contextOverrides = {}) => {
    isAuthenticated.mockReturnValue(true);
    const value = {
        ...defaultUseCartValue,
        cart: makeCart(cartOverrides),
        fetchCart: vi.fn(),
        updateItem: vi.fn().mockResolvedValue({ success: true }),
        removeItem: vi.fn().mockResolvedValue({ success: true }),
        clearCart: vi.fn().mockResolvedValue({ success: true }),
        applyCoupon: vi.fn().mockResolvedValue({ success: true }),
        removeCoupon: vi.fn().mockResolvedValue({ success: true }),
        ...contextOverrides,
    };
    useCart.mockReturnValue(value);
    return value;
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

    // ── Coupon (server-backed; Task 9.1.1.9) ─────────────────────────────────
    // The page holds no coupon state of its own: it reads coupon_code /
    // coupon_discount / coupon_error from the cart and calls the context's
    // applyCoupon / removeCoupon.

    describe('coupon', () => {
        const typeAndApply = async (user, code) => {
            await user.type(screen.getByPlaceholderText(/coupon code/i), code);
            await user.click(screen.getByRole('button', { name: /apply coupon/i }));
        };

        it('shows the coupon entry form when no coupon is attached', () => {
            setupAuthenticated();

            renderCart();

            expect(screen.getByPlaceholderText(/coupon code/i)).toBeInTheDocument();
            expect(screen.getByRole('button', { name: /apply coupon/i })).toBeInTheDocument();
            expect(screen.queryByText(/^Coupon \(/)).not.toBeInTheDocument();
        });

        it('sends the typed code through the context applyCoupon (not a client-side check)', async () => {
            const user = userEvent.setup();
            const ctx = setupAuthenticated({ subtotal: '100.00', total_items: 1 });

            renderCart();
            await typeAndApply(user, 'SUMMER20');

            expect(ctx.applyCoupon).toHaveBeenCalledTimes(1);
            expect(ctx.applyCoupon).toHaveBeenCalledWith('SUMMER20');
        });

        it('shows a success toast after a coupon is applied', async () => {
            const user = userEvent.setup();
            setupAuthenticated();

            renderCart();
            await typeAndApply(user, 'SUMMER20');

            expect(await screen.findByText('Coupon applied.')).toBeInTheDocument();
        });

        it('no longer accepts the old hardcoded DISCOUNT20 code on its own', async () => {
            const user = userEvent.setup();
            // The server (mocked here) is the only authority on validity.
            setupAuthenticated(
                { subtotal: '100.00', total_items: 1 },
                {
                    applyCoupon: vi.fn().mockResolvedValue({
                        success: false,
                        message: 'Invalid coupon code.',
                    }),
                },
            );

            renderCart();
            await typeAndApply(user, 'DISCOUNT20');

            expect(await screen.findByText('Invalid coupon code.')).toBeInTheDocument();
            expect(screen.queryByText('-$20.00')).not.toBeInTheDocument();
        });

        it('shows the backend’s specific rejection message inline, without applying anything', async () => {
            const user = userEvent.setup();
            setupAuthenticated(
                { subtotal: '100.00', total_items: 1 },
                {
                    applyCoupon: vi.fn().mockResolvedValue({
                        success: false,
                        message: 'This coupon has expired.',
                    }),
                },
            );

            renderCart();
            await typeAndApply(user, 'OLDCODE');

            expect(await screen.findByRole('alert')).toHaveTextContent('This coupon has expired.');
            expect(screen.queryByText(/^Coupon \(/)).not.toBeInTheDocument();
            expect(screen.queryByText('Coupon applied.')).not.toBeInTheDocument();
        });

        it('shows the applied code, a discount line and the reduced total', () => {
            // subtotal 100, standard shipping 4.99, tax 10.00, discount 10.00
            setupAuthenticated({
                subtotal: '100.00',
                total_items: 1,
                coupon_code: 'SUMMER20',
                coupon_discount: '10.00',
                coupon_error: null,
            });

            renderCart();

            expect(screen.getByText(/SUMMER20/, { selector: 'strong' })).toBeInTheDocument();
            expect(screen.getByText('Coupon (SUMMER20)')).toBeInTheDocument();
            expect(screen.getByText('-$10.00')).toBeInTheDocument();
            expect(screen.getByText('$104.99')).toBeInTheDocument();
            // Entry form is replaced by the applied state.
            expect(screen.queryByPlaceholderText(/coupon code/i)).not.toBeInTheDocument();
        });

        it('restores the undiscounted total when the cart has no coupon', () => {
            setupAuthenticated({
                subtotal: '100.00',
                total_items: 1,
                coupon_code: null,
                coupon_discount: '0',
                coupon_error: null,
            });

            renderCart();

            expect(screen.queryByText('-$10.00')).not.toBeInTheDocument();
            expect(screen.getByText('$114.99')).toBeInTheDocument(); // 100 + 4.99 + 10.00
        });

        it('removes the coupon through the context and shows a toast', async () => {
            const user = userEvent.setup();
            const ctx = setupAuthenticated({
                subtotal: '100.00',
                total_items: 1,
                coupon_code: 'SUMMER20',
                coupon_discount: '10.00',
                coupon_error: null,
            });

            renderCart();
            await user.click(screen.getByRole('button', { name: /remove coupon SUMMER20/i }));

            expect(ctx.removeCoupon).toHaveBeenCalledTimes(1);
            expect(await screen.findByText('Coupon removed.')).toBeInTheDocument();
        });

        describe('attached coupon that has since become invalid', () => {
            const invalidCart = {
                subtotal: '100.00',
                total_items: 1,
                coupon_code: 'SUMMER20',
                coupon_discount: '0',
                coupon_error: 'This coupon has expired.',
            };

            it('shows the reason clearly instead of ignoring it', () => {
                setupAuthenticated(invalidCart);

                renderCart();

                expect(screen.getByText(/SUMMER20 can.t be applied/)).toBeInTheDocument();
                expect(screen.getByText('This coupon has expired.')).toBeInTheDocument();
            });

            it('does not subtract anything from the total', () => {
                setupAuthenticated({ ...invalidCart, coupon_discount: '10.00' });

                renderCart();

                expect(screen.queryByText(/^Coupon \(/)).not.toBeInTheDocument();
                expect(screen.queryByText('-$10.00')).not.toBeInTheDocument();
                expect(screen.getByText('$114.99')).toBeInTheDocument();
            });

            it('offers a way to remove it, which calls removeCoupon', async () => {
                const user = userEvent.setup();
                const ctx = setupAuthenticated(invalidCart);

                renderCart();
                await user.click(screen.getByRole('button', { name: /remove coupon/i }));

                expect(ctx.removeCoupon).toHaveBeenCalledTimes(1);
                expect(await screen.findByText('Coupon removed.')).toBeInTheDocument();
            });
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