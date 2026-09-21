import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import AddressPicker from '../components/AddressPicker';
import { NEW_ADDRESS, formatAddress } from '../utils/address';

// ─── Mocks (for the Checkout integration half of this file) ──────────────────

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../context/CartContext', () => ({ useCart: vi.fn() }));

vi.mock('../services/api', () => ({
  createOrder: vi.fn(),
  isAuthenticated: vi.fn(),
  dashboardAPI: { getAddresses: vi.fn() },
}));

import Checkout from '../pages/Checkout';
import { useCart } from '../context/CartContext';
import { createOrder, isAuthenticated, dashboardAPI } from '../services/api';

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const ADDRESS_A = {
  id: 11,
  label: 'home',
  full_name: 'Jane Doe',
  phone: '555-0100',
  address_line: '12 Valiasr St',
  apartment: 'Apt 4',
  city: 'Tehran',
  province: 'tehran',
  postal_code: '1234567890',
  country: 'IR',
  is_default: true,
};

const ADDRESS_B = {
  id: 22,
  label: 'office',
  full_name: 'Jane Doe',
  phone: '555-0200',
  address_line: '9 Chahar Bagh Ave',
  apartment: '',
  city: 'Isfahan',
  province: 'isfahan',
  postal_code: '9876543210',
  country: 'IR',
  is_default: false,
};

const MOCK_CART = {
  subtotal: '89.97',
  total_items: 3,
  items: [
    {
      id: 1,
      quantity: 2,
      unit_price: '19.99',
      subtotal: '39.98',
      product: { id: 10, name: 'Test Widget', image: null },
    },
  ],
};

const CART_READY_STATE = {
  cart: MOCK_CART,
  loading: false,
  error: null,
  fetchCart: vi.fn(),
  clearCart: vi.fn(),
};

// ═════════════════════════════════════════════════════════════════════════════
// 1. AddressPicker in isolation
// ═════════════════════════════════════════════════════════════════════════════
describe('AddressPicker', () => {
  it('renders nothing when there are no saved addresses', () => {
    const { container } = render(
      <AddressPicker addresses={[]} selectedId={NEW_ADDRESS} onSelect={vi.fn()} />,
    );
    // A picker whose only option is "enter a new address" is noise — the
    // caller's manual form is the entire UI in that case.
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByTestId('address-picker')).not.toBeInTheDocument();
  });

  it('renders nothing when addresses prop is omitted entirely', () => {
    const { container } = render(
      <AddressPicker selectedId={NEW_ADDRESS} onSelect={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders a skeleton while addresses are loading', () => {
    render(
      <AddressPicker addresses={[]} selectedId={NEW_ADDRESS} onSelect={vi.fn()} loading />,
    );
    expect(screen.getByTestId('address-picker-loading')).toBeInTheDocument();
    expect(screen.queryByTestId('address-picker')).not.toBeInTheDocument();
  });

  it('renders one radio per saved address plus an "enter a new address" option', () => {
    render(
      <AddressPicker
        addresses={[ADDRESS_A, ADDRESS_B]}
        selectedId={ADDRESS_A.id}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByTestId('address-picker')).toBeInTheDocument();
    // 2 saved + 1 "new" = 3 radios
    expect(screen.getAllByRole('radio')).toHaveLength(3);
    expect(screen.getByText(/enter a new address/i)).toBeInTheDocument();
  });

  it('shows each address formatted, including its province label and postal code', () => {
    render(
      <AddressPicker
        addresses={[ADDRESS_A, ADDRESS_B]}
        selectedId={ADDRESS_A.id}
        onSelect={vi.fn()}
      />,
    );

    // Province is stored as a slug ("tehran") but must display as its
    // human label ("Tehran").
    expect(screen.getByText(/12 Valiasr St, Apt 4, Tehran, Tehran 1234567890/)).toBeInTheDocument();
    expect(screen.getByText(/9 Chahar Bagh Ave, Isfahan, Isfahan 9876543210/)).toBeInTheDocument();
  });

  it('marks the default address with a Default badge', () => {
    render(
      <AddressPicker addresses={[ADDRESS_A, ADDRESS_B]} selectedId={ADDRESS_A.id} onSelect={vi.fn()} />,
    );
    expect(screen.getByText('Default')).toBeInTheDocument();
  });

  it('checks the radio matching selectedId', () => {
    render(
      <AddressPicker addresses={[ADDRESS_A, ADDRESS_B]} selectedId={ADDRESS_B.id} onSelect={vi.fn()} />,
    );
    const radios = screen.getAllByRole('radio');
    expect(radios.find((r) => r.value === String(ADDRESS_B.id))).toBeChecked();
    expect(radios.find((r) => r.value === String(ADDRESS_A.id))).not.toBeChecked();
  });

  it('calls onSelect with the address id when a saved address is chosen', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <AddressPicker addresses={[ADDRESS_A, ADDRESS_B]} selectedId={ADDRESS_A.id} onSelect={onSelect} />,
    );

    const radios = screen.getAllByRole('radio');
    await user.click(radios.find((r) => r.value === String(ADDRESS_B.id)));

    expect(onSelect).toHaveBeenCalledWith(ADDRESS_B.id);
  });

  it('calls onSelect with NEW_ADDRESS when "enter a new address" is chosen', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <AddressPicker addresses={[ADDRESS_A]} selectedId={ADDRESS_A.id} onSelect={onSelect} />,
    );

    await user.click(screen.getByText(/enter a new address/i));

    expect(onSelect).toHaveBeenCalledWith(NEW_ADDRESS);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 2. formatAddress helper
// ═════════════════════════════════════════════════════════════════════════════
describe('formatAddress', () => {
  it('omits an empty apartment without leaving a stray comma', () => {
    expect(formatAddress(ADDRESS_B)).toBe(
      '9 Chahar Bagh Ave, Isfahan, Isfahan 9876543210',
    );
  });

  it('returns an empty string for a null/undefined address', () => {
    expect(formatAddress(null)).toBe('');
    expect(formatAddress(undefined)).toBe('');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 3. Picker wired into Checkout
// ═════════════════════════════════════════════════════════════════════════════
describe('Checkout saved-address integration', () => {
  const renderCheckout = () =>
    render(
      <MemoryRouter>
        <Checkout />
      </MemoryRouter>,
    );

  beforeEach(() => {
    vi.clearAllMocks();
    isAuthenticated.mockReturnValue(true);
    useCart.mockReturnValue(CART_READY_STATE);
    dashboardAPI.getAddresses.mockResolvedValue({ data: [] });
  });

  it('shows no picker when the shopper has no saved addresses', async () => {
    renderCheckout();

    await waitFor(() => expect(dashboardAPI.getAddresses).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.queryByTestId('address-picker-loading')).not.toBeInTheDocument(),
    );

    expect(screen.queryByTestId('address-picker')).not.toBeInTheDocument();
    // ...and the manual form is present instead.
    expect(document.querySelector('[name="address"]')).toBeInTheDocument();
  });

  it('shows the picker and hides the manual form when addresses exist', async () => {
    dashboardAPI.getAddresses.mockResolvedValue({ data: [ADDRESS_A, ADDRESS_B] });
    renderCheckout();

    expect(await screen.findByTestId('address-picker')).toBeInTheDocument();
    // The default address is preselected, so the manual fields are hidden.
    expect(document.querySelector('[name="address"]')).not.toBeInTheDocument();
  });

  it('preselects the shopper\'s default address', async () => {
    dashboardAPI.getAddresses.mockResolvedValue({ data: [ADDRESS_B, ADDRESS_A] });
    renderCheckout();

    await screen.findByTestId('address-picker');
    const radios = screen.getAllByRole('radio').filter((r) => r.name === 'saved_address');
    // ADDRESS_A is is_default: true, even though B comes first in the list.
    expect(radios.find((r) => r.value === String(ADDRESS_A.id))).toBeChecked();
  });

  it('reveals the manual form fields when "enter a new address" is chosen', async () => {
    dashboardAPI.getAddresses.mockResolvedValue({ data: [ADDRESS_A] });
    const user = userEvent.setup();
    renderCheckout();

    await screen.findByTestId('address-picker');
    expect(document.querySelector('[name="address"]')).not.toBeInTheDocument();

    await user.click(screen.getByText(/enter a new address/i));

    await waitFor(() =>
      expect(document.querySelector('[name="address"]')).toBeInTheDocument(),
    );
    expect(document.querySelector('[name="city"]')).toBeInTheDocument();
    expect(document.querySelector('[name="state"]')).toBeInTheDocument();
    expect(document.querySelector('[name="zip"]')).toBeInTheDocument();
    // The "save this address" opt-in only makes sense for a new address.
    expect(screen.getByText(/save this address for future orders/i)).toBeInTheDocument();
  });

  it('submits address_id (and no manual address fields) when a saved address is used', async () => {
    dashboardAPI.getAddresses.mockResolvedValue({ data: [ADDRESS_A] });
    createOrder.mockResolvedValueOnce({ data: { id: 7 } });
    const user = userEvent.setup();
    renderCheckout();

    await screen.findByTestId('address-picker');

    // Email is still required — it isn't part of a saved Address.
    await user.type(document.querySelector('[name="email"]'), 'jane@example.com');
    await user.click(document.querySelector('[name="terms"]'));

    await user.click(screen.getByRole('button', { name: /place order/i }));

    await waitFor(() => expect(createOrder).toHaveBeenCalledOnce());
    const [payload] = createOrder.mock.calls[0];

    expect(payload.address_id).toBe(ADDRESS_A.id);
    // The two payload shapes are mutually exclusive — sending manual
    // fields alongside address_id would be ambiguous about intent.
    expect(payload).not.toHaveProperty('address');
    expect(payload).not.toHaveProperty('state');
    expect(payload).not.toHaveProperty('zip');
    expect(payload).not.toHaveProperty('save_address');
  });

  it('does not require manual address fields when a saved address is selected', async () => {
    dashboardAPI.getAddresses.mockResolvedValue({ data: [ADDRESS_A] });
    createOrder.mockResolvedValueOnce({ data: { id: 8 } });
    const user = userEvent.setup();
    renderCheckout();

    await screen.findByTestId('address-picker');

    // Deliberately fill ONLY email + terms. If validation still demanded
    // first/last/phone/address/city/province/zip, this submit would
    // never reach createOrder.
    await user.type(document.querySelector('[name="email"]'), 'jane@example.com');
    await user.click(document.querySelector('[name="terms"]'));

    await user.click(screen.getByRole('button', { name: /place order/i }));

    await waitFor(() => expect(createOrder).toHaveBeenCalledOnce());
  });

  it('sends save_address: true when the new-address opt-in is checked', async () => {
    dashboardAPI.getAddresses.mockResolvedValue({ data: [ADDRESS_A] });
    createOrder.mockResolvedValueOnce({ data: { id: 9 } });
    const user = userEvent.setup();
    renderCheckout();

    await screen.findByTestId('address-picker');
    await user.click(screen.getByText(/enter a new address/i));
    await waitFor(() =>
      expect(document.querySelector('[name="address"]')).toBeInTheDocument(),
    );

    await user.type(document.querySelector('[name="firstName"]'), 'Jane');
    await user.type(document.querySelector('[name="lastName"]'), 'Doe');
    await user.type(document.querySelector('[name="email"]'), 'jane@example.com');
    await user.type(document.querySelector('[name="phone"]'), '555-0100');
    await user.type(document.querySelector('[name="address"]'), '1 New St');
    await user.type(document.querySelector('[name="city"]'), 'Shiraz');
    await user.selectOptions(document.querySelector('[name="state"]'), 'fars');
    await user.type(document.querySelector('[name="zip"]'), '1112223334');
    await user.click(document.querySelector('[name="saveAddress"]'));

    await user.click(document.querySelector('[name="terms"]'));

    await user.click(screen.getByRole('button', { name: /place order/i }));

    await waitFor(() => expect(createOrder).toHaveBeenCalledOnce());
    const [payload] = createOrder.mock.calls[0];
    expect(payload.save_address).toBe(true);
    expect(payload.state).toBe('fars');
    expect(payload).not.toHaveProperty('address_id');
  });

  it('rejects a postal code that is not exactly 10 digits', async () => {
    dashboardAPI.getAddresses.mockResolvedValue({ data: [] });
    const user = userEvent.setup();
    renderCheckout();

    await waitFor(() =>
      expect(document.querySelector('[name="zip"]')).toBeInTheDocument(),
    );

    await user.type(document.querySelector('[name="zip"]'), '12345');
    await user.click(screen.getByRole('button', { name: /place order/i }));

    expect(
      await screen.findByText(/valid 10-digit iranian postal code/i),
    ).toBeInTheDocument();
    expect(createOrder).not.toHaveBeenCalled();
  });

  it('falls back to the manual form if the address fetch fails', async () => {
    dashboardAPI.getAddresses.mockRejectedValue(new Error('network'));
    renderCheckout();

    await waitFor(() =>
      expect(document.querySelector('[name="address"]')).toBeInTheDocument(),
    );
    expect(screen.queryByTestId('address-picker')).not.toBeInTheDocument();
  });
});
