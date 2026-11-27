// PaymentMethodsTab.jsx is now the customer's PAYMENT HISTORY (real PaymentTransaction
// rows from GET /dashboard/customer/payment-history/), not a summary derived from
// order.payment_method. "Own records only" is enforced server-side
// (backend/dashboard/tests/test_payment_history.py); here we pin that the SPA asks
// only that endpoint and never tries to widen or fake the scope.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../services/api', () => ({
  dashboardAPI: { getPaymentHistory: vi.fn(), getOrders: vi.fn() },
}));

import PaymentMethodsTab from '../components/PaymentMethodsTab';
import { dashboardAPI } from '../services/api';

const txn = (over = {}) => ({
  id: 1,
  order_id: 7,
  order_number: 'ORD-1001',
  gateway: 'zarinpal',
  gateway_display: 'ZarinPal',
  status: 'success',
  status_display: 'Success',
  amount: 299_900,
  ref_id: 'REF-555',
  created_at: '2026-01-15T12:00:00Z',
  ...over,
});

describe('PaymentMethodsTab (Payment History)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches from the payment-history endpoint only — not from order history', async () => {
    dashboardAPI.getPaymentHistory.mockResolvedValue({ data: { count: 1, results: [txn()] } });
    render(<PaymentMethodsTab />);
    await screen.findByText('ORD-1001');
    expect(dashboardAPI.getPaymentHistory).toHaveBeenCalledTimes(1);
    // Scope can only be page/page_size: no user/order id is ever sent by the client.
    expect(Object.keys(dashboardAPI.getPaymentHistory.mock.calls[0][0]).sort()).toEqual(['page', 'page_size']);
    expect(dashboardAPI.getOrders).not.toHaveBeenCalled();
  });

  it('shows gateway, status, reference and a Toman amount per transaction', async () => {
    dashboardAPI.getPaymentHistory.mockResolvedValue({
      data: {
        count: 2,
        results: [
          txn(),
          txn({ id: 2, order_number: 'ORD-1002', gateway: 'zibal', gateway_display: 'Zibal',
                status: 'failed', status_display: 'Failed', amount: 150_000, ref_id: '' }),
        ],
      },
    });
    render(<PaymentMethodsTab />);
    const rows = await screen.findAllByTestId('payment-row');
    expect(rows).toHaveLength(2);

    expect(within(rows[0]).getByText('ORD-1001')).toBeInTheDocument();
    expect(within(rows[0]).getByText('ZarinPal')).toBeInTheDocument();
    expect(within(rows[0]).getByText('Success')).toBeInTheDocument();
    expect(within(rows[0]).getByText(/REF-555/)).toBeInTheDocument();
    // 299,900 Rial -> 29,990 Toman (never "$299,900.00")
    expect(within(rows[0]).getByText('29,990 تومان')).toBeInTheDocument();

    expect(within(rows[1]).getByText('Zibal')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Failed')).toBeInTheDocument();
    expect(within(rows[1]).getByText('15,000 تومان')).toBeInTheDocument();
    expect(within(rows[1]).queryByText(/Ref:/)).toBeNull();
    expect(document.body.textContent).not.toMatch(/[$]/);
  });

  it('no longer fabricates "payment methods" from order history', async () => {
    dashboardAPI.getPaymentHistory.mockResolvedValue({ data: { count: 1, results: [txn()] } });
    render(<PaymentMethodsTab />);
    await screen.findByText('ORD-1001');
    expect(screen.getByRole('heading', { name: 'Payment History' })).toBeInTheDocument();
    expect(screen.queryByText(/Payment Methods/i)).toBeNull();
    expect(screen.queryByText(/Credit \/ Debit Card|PayPal|Cash on Delivery/)).toBeNull();
  });

  it('shows an empty state when there are no transactions', async () => {
    dashboardAPI.getPaymentHistory.mockResolvedValue({ data: { count: 0, results: [] } });
    render(<PaymentMethodsTab />);
    expect(await screen.findByTestId('payment-history-empty')).toBeInTheDocument();
  });

  it('shows an error (not the empty state) when the request fails, and can retry', async () => {
    dashboardAPI.getPaymentHistory.mockRejectedValueOnce(new Error('500'));
    dashboardAPI.getPaymentHistory.mockResolvedValueOnce({ data: { count: 1, results: [txn()] } });
    const user = userEvent.setup();
    render(<PaymentMethodsTab />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
    expect(screen.queryByTestId('payment-history-empty')).toBeNull();

    await user.click(screen.getByRole('button', { name: /try again/i }));
    expect(await screen.findByText('ORD-1001')).toBeInTheDocument();
  });

  it('paginates through the server pages', async () => {
    dashboardAPI.getPaymentHistory
      .mockResolvedValueOnce({ data: { count: 12, results: [txn()] } })
      .mockResolvedValueOnce({ data: { count: 12, results: [txn({ id: 11, order_number: 'ORD-2000' })] } });
    const user = userEvent.setup();
    render(<PaymentMethodsTab />);
    await screen.findByText('ORD-1001');
    expect(screen.getByText('1 / 2')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /next page/i }));
    expect(await screen.findByText('ORD-2000')).toBeInTheDocument();
    expect(dashboardAPI.getPaymentHistory).toHaveBeenLastCalledWith({ page: 2, page_size: 10 });
  });
});
