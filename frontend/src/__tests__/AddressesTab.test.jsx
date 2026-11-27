import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../services/api', () => ({
  dashboardAPI: {
    getAddresses: vi.fn(),
    createAddress: vi.fn(),
    updateAddress: vi.fn(),
    deleteAddress: vi.fn(),
  },
}));

import AddressesTab from '../components/AddressesTab';
import { dashboardAPI } from '../services/api';
import { IRAN_PROVINCES } from '../constants/provinces';

const addr = (over = {}) => ({
  id: 1,
  label: 'home',
  first_name: 'Sara',
  last_name: 'Ahmadi',
  full_name: 'Sara Ahmadi',
  phone: '09121234567',
  address_line: '12 Valiasr St',
  apartment: '',
  city: 'Tehran',
  province: 'tehran',
  postal_code: '1234567890',
  country: 'IR',
  is_default: true,
  ...over,
});

const setup = async (list = [addr()]) => {
  dashboardAPI.getAddresses.mockResolvedValue({ data: { results: list } });
  const user = userEvent.setup();
  render(<AddressesTab />);
  await screen.findByRole('heading', { name: 'My Addresses' });
  await waitFor(() => expect(dashboardAPI.getAddresses).toHaveBeenCalled());
  return user;
};

const openNewForm = async (user) => {
  await user.click(screen.getByRole('button', { name: /^add address$/i }));
  return screen.findByRole('heading', { name: 'Add New Address' });
};

// The header "Add Address" button and the form's submit share a name; target the form's.
const submit = (user) => user.click(document.querySelector('form button[type="submit"]'));

const fillValid = async (user, over = {}) => {
  const v = { first_name: 'Ali', last_name: 'Rezai', phone: '09120000000',
    address_line: '5 Azadi Ave', city: 'Shiraz', postal_code: '7123456789', ...over };
  for (const [name, value] of Object.entries(v)) {
    await user.type(document.getElementById(`addr-${name}`), value);
  }
  await user.selectOptions(screen.getByLabelText('Province'), 'fars');
};

describe('AddressesTab — form fields', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders province as a select with all 31 Iran provinces', async () => {
    const user = await setup([]);
    await openNewForm(user);
    const select = screen.getByLabelText('Province');
    expect(select.tagName).toBe('SELECT');
    const options = within(select).getAllByRole('option').filter((o) => o.value !== '');
    expect(options).toHaveLength(31);
    expect(options.map((o) => o.value)).toEqual(IRAN_PROVINCES.map((p) => p.value));
  });

  it('uses postal_code and has no state / zip / country inputs', async () => {
    const user = await setup([]);
    await openNewForm(user);
    expect(screen.getByLabelText(/postal code/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^state/i)).toBeNull();
    expect(screen.queryByLabelText(/zip/i)).toBeNull();
    expect(screen.queryByLabelText(/country/i)).toBeNull();
  });
});

describe('AddressesTab — create / validation', () => {
  beforeEach(() => vi.clearAllMocks());

  it('sends province/postal_code (not state/zip_code) and country IR', async () => {
    dashboardAPI.createAddress.mockResolvedValue({ data: addr({ id: 2 }) });
    const user = await setup([]);
    await openNewForm(user);
    await fillValid(user);
    await submit(user);

    await waitFor(() => expect(dashboardAPI.createAddress).toHaveBeenCalledTimes(1));
    const payload = dashboardAPI.createAddress.mock.calls[0][0];
    expect(payload).toMatchObject({ province: 'fars', postal_code: '7123456789', country: 'IR', city: 'Shiraz' });
    expect(payload).not.toHaveProperty('state');
    expect(payload).not.toHaveProperty('zip_code');
  });

  it.each(['12345', '12345678901', 'abcdefghij', '12345 6789'])(
    'rejects postal code %j client-side, before any request',
    async (bad) => {
      const user = await setup([]);
      await openNewForm(user);
      await fillValid(user, { postal_code: bad });
      await submit(user);

      expect(await screen.findByText(/valid 10-digit/i)).toBeInTheDocument();
      expect(dashboardAPI.createAddress).not.toHaveBeenCalled();
    },
  );

  it('requires a province and the other mandatory fields', async () => {
    const user = await setup([]);
    await openNewForm(user);
    await submit(user);
    expect((await screen.findAllByText('Required')).length).toBeGreaterThanOrEqual(6);
    expect(dashboardAPI.createAddress).not.toHaveBeenCalled();
  });

  it('accepts Persian digits and sends Western digits', async () => {
    dashboardAPI.createAddress.mockResolvedValue({ data: addr({ id: 2 }) });
    const user = await setup([]);
    await openNewForm(user);
    await fillValid(user, { postal_code: '۷۱۲۳۴۵۶۷۸۹' });
    await submit(user);
    await waitFor(() => expect(dashboardAPI.createAddress).toHaveBeenCalled());
    expect(dashboardAPI.createAddress.mock.calls[0][0].postal_code).toBe('7123456789');
  });

  it('shows a backend field error under the field and keeps the form open', async () => {
    dashboardAPI.createAddress.mockRejectedValue({
      response: { status: 400, data: { postal_code: ['Postal code must be exactly 10 digits.'] } },
    });
    const user = await setup([]);
    await openNewForm(user);
    await fillValid(user);
    await submit(user);

    expect(await screen.findByText('Postal code must be exactly 10 digits.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Add New Address' })).toBeInTheDocument();
  });

  it('shows non-field and network failures in a banner instead of failing silently', async () => {
    dashboardAPI.createAddress.mockRejectedValueOnce({ response: { status: 403, data: { detail: 'Not allowed.' } } });
    dashboardAPI.createAddress.mockRejectedValueOnce(new Error('Network Error'));
    const user = await setup([]);
    await openNewForm(user);
    await fillValid(user);
    await submit(user);
    expect(await screen.findByRole('alert')).toHaveTextContent('Not allowed.');

    await submit(user);
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/could not save/i));
  });
});

describe('AddressesTab — address cards', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows the province label (not the raw key), postal code and country name', async () => {
    await setup([
      addr(),
      addr({ id: 2, is_default: false, province: 'khorasan_razavi', city: 'Mashhad', postal_code: '9188888888' }),
    ]);
    const cards = await screen.findAllByTestId('address-card');
    expect(within(cards[0]).getByText('Tehran, Tehran 1234567890')).toBeInTheDocument();
    expect(within(cards[1]).getByText('Mashhad, Khorasan Razavi 9188888888')).toBeInTheDocument();
    expect(within(cards[1]).getByText('Iran')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/khorasan_razavi|zip|\bIR\b/);
  });

  it('shows an error with retry when the list fails to load (not "No addresses")', async () => {
    dashboardAPI.getAddresses.mockRejectedValueOnce(new Error('500'));
    dashboardAPI.getAddresses.mockResolvedValueOnce({ data: { results: [addr()] } });
    const user = userEvent.setup();
    render(<AddressesTab />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
    expect(screen.queryByText('No addresses saved')).toBeNull();
    await user.click(screen.getByRole('button', { name: /try again/i }));
    expect(await screen.findByTestId('address-card')).toBeInTheDocument();
  });

  it('shows the empty state when there are no addresses', async () => {
    await setup([]);
    expect(await screen.findByText('No addresses saved')).toBeInTheDocument();
  });
});

describe('AddressesTab — default address', () => {
  beforeEach(() => vi.clearAllMocks());

  it('badges only the default and offers "Set Default" on the others', async () => {
    await setup([addr(), addr({ id: 2, is_default: false, label: 'office' })]);
    const [first, second] = await screen.findAllByTestId('address-card');
    expect(within(first).getByText('Default')).toBeInTheDocument();
    expect(within(first).queryByRole('button', { name: /set default/i })).toBeNull();
    expect(within(second).queryByText('Default')).toBeNull();
    expect(within(second).getByRole('button', { name: /set default/i })).toBeInTheDocument();
  });

  it('PATCHes is_default and reflects the new default after the refetch', async () => {
    dashboardAPI.updateAddress.mockResolvedValue({ data: {} });
    dashboardAPI.getAddresses
      .mockResolvedValueOnce({ data: { results: [addr(), addr({ id: 2, is_default: false, label: 'office' })] } })
      .mockResolvedValueOnce({ data: { results: [addr({ id: 2, label: 'office' }), addr({ is_default: false })] } });
    const user = userEvent.setup();
    render(<AddressesTab />);
    const [, second] = await screen.findAllByTestId('address-card');
    await user.click(within(second).getByRole('button', { name: /set default/i }));

    expect(dashboardAPI.updateAddress).toHaveBeenCalledWith(2, { is_default: true });
    await waitFor(() => {
      const cards = screen.getAllByTestId('address-card');
      expect(cards[0].dataset.default).toBe('true');
      expect(within(cards[0]).getByText('office')).toBeInTheDocument();
      expect(cards[1].dataset.default).toBe('false');
    });
    expect(screen.getAllByText('Default')).toHaveLength(1);
  });

  it('reports a failed default change and leaves the state alone', async () => {
    dashboardAPI.updateAddress.mockRejectedValue(new Error('500'));
    const user = await setup([addr(), addr({ id: 2, is_default: false })]);
    const [, second] = await screen.findAllByTestId('address-card');
    await user.click(within(second).getByRole('button', { name: /set default/i }));
    expect(await screen.findByText('Failed to update')).toBeInTheDocument();
    expect(dashboardAPI.getAddresses).toHaveBeenCalledTimes(1);
  });
});

describe('AddressesTab — edit / delete', () => {
  beforeEach(() => vi.clearAllMocks());

  it('edits an existing address, prefilled, PATCHing province/postal_code', async () => {
    dashboardAPI.updateAddress.mockResolvedValue({ data: {} });
    const user = await setup();
    await user.click(await screen.findByRole('button', { name: /edit/i }));
    expect(screen.getByLabelText('Province')).toHaveValue('tehran');
    const postal = document.getElementById('addr-postal_code');
    expect(postal).toHaveValue('1234567890');
    await user.clear(postal);
    await user.type(postal, '1111111111');
    await user.click(screen.getByRole('button', { name: 'Save Changes' }));
    await waitFor(() => expect(dashboardAPI.updateAddress).toHaveBeenCalledTimes(1));
    const [id, payload] = dashboardAPI.updateAddress.mock.calls[0];
    expect(id).toBe(1);
    expect(payload).toMatchObject({ province: 'tehran', postal_code: '1111111111', country: 'IR' });
  });

  it('deletes only after confirmation', async () => {
    dashboardAPI.deleteAddress.mockResolvedValue({});
    const user = await setup();
    const confirm = vi.spyOn(window, 'confirm');
    confirm.mockReturnValueOnce(false);
    await user.click(await screen.findByRole('button', { name: /delete/i }));
    expect(dashboardAPI.deleteAddress).not.toHaveBeenCalled();

    confirm.mockReturnValueOnce(true);
    await user.click(screen.getByRole('button', { name: /delete/i }));
    await waitFor(() => expect(dashboardAPI.deleteAddress).toHaveBeenCalledWith(1));
    expect(await screen.findByText('No addresses saved')).toBeInTheDocument();
    confirm.mockRestore();
  });
});
