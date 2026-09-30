import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ShippingOptionPicker from '../components/ShippingOptionPicker';

const OPTIONS = [
  {
    carrier_id: 1,
    carrier_name: 'Iran Post',
    rate_id: 10,
    price: '45000.00',
    estimated_days_min: 2,
    estimated_days_max: 4,
  },
  {
    carrier_id: 2,
    carrier_name: 'Tipax',
    rate_id: 20,
    price: '65000.00',
    estimated_days_min: 1,
    estimated_days_max: 2,
  },
];

describe('ShippingOptionPicker', () => {
  // ── Renders options correctly ─────────────────────────────────────────────
  describe('rendering options', () => {
    it('renders one radio per option', () => {
      render(<ShippingOptionPicker options={OPTIONS} onSelect={vi.fn()} />);

      expect(screen.getByTestId('shipping-options')).toBeInTheDocument();
      expect(screen.getAllByRole('radio')).toHaveLength(2);
    });

    it('shows each carrier name, formatted price, and estimated delivery window', () => {
      render(<ShippingOptionPicker options={OPTIONS} onSelect={vi.fn()} />);

      expect(screen.getByText('Iran Post')).toBeInTheDocument();
      expect(screen.getByText('$45000.00')).toBeInTheDocument();
      expect(screen.getByText('2–4 days')).toBeInTheDocument();

      expect(screen.getByText('Tipax')).toBeInTheDocument();
      expect(screen.getByText('$65000.00')).toBeInTheDocument();
      expect(screen.getByText('1–2 days')).toBeInTheDocument();
    });

    it('renders a singular "day" label when min and max are equal', () => {
      render(
        <ShippingOptionPicker
          options={[{ ...OPTIONS[0], estimated_days_min: 1, estimated_days_max: 1 }]}
          onSelect={vi.fn()}
        />,
      );

      expect(screen.getByText('1 day')).toBeInTheDocument();
    });

    it('checks the radio matching the selected option', () => {
      render(
        <ShippingOptionPicker
          options={OPTIONS}
          selected={{ carrier_id: 2, rate_id: 20 }}
          onSelect={vi.fn()}
        />,
      );

      const radios = screen.getAllByRole('radio');
      expect(radios.find((r) => r.value === '2-20')).toBeChecked();
      expect(radios.find((r) => r.value === '1-10')).not.toBeChecked();
    });

    it('renders no radios and no empty/error state when options is empty but loading', () => {
      render(<ShippingOptionPicker options={[]} loading onSelect={vi.fn()} />);

      expect(screen.getByTestId('shipping-options-loading')).toBeInTheDocument();
      expect(screen.queryByRole('radio')).not.toBeInTheDocument();
      expect(screen.queryByTestId('shipping-options-empty')).not.toBeInTheDocument();
    });
  });

  // ── Selecting one updates form state (via onSelect) ───────────────────────
  describe('selecting an option', () => {
    it('calls onSelect with the full option object when a radio is chosen', async () => {
      const onSelect = vi.fn();
      const user = userEvent.setup();
      render(<ShippingOptionPicker options={OPTIONS} onSelect={onSelect} />);

      const radios = screen.getAllByRole('radio');
      await user.click(radios.find((r) => r.value === '2-20'));

      expect(onSelect).toHaveBeenCalledWith(OPTIONS[1]);
    });

    it('calling onSelect with a different option updates which radio is checked', async () => {
      const onSelect = vi.fn();
      const user = userEvent.setup();
      const { rerender } = render(
        <ShippingOptionPicker options={OPTIONS} selected={null} onSelect={onSelect} />,
      );

      const firstRadio = screen.getAllByRole('radio')[0];
      await user.click(firstRadio);
      expect(onSelect).toHaveBeenCalledWith(OPTIONS[0]);

      // Simulate the parent (Checkout.jsx) updating its form state in
      // response to onSelect and passing the new `selected` prop back down.
      rerender(
        <ShippingOptionPicker
          options={OPTIONS}
          selected={{ carrier_id: OPTIONS[0].carrier_id, rate_id: OPTIONS[0].rate_id }}
          onSelect={onSelect}
        />,
      );

      expect(screen.getAllByRole('radio')[0]).toBeChecked();
    });
  });

  // ── Empty-options fallback ─────────────────────────────────────────────────
  describe('empty options', () => {
    it('shows the "not currently available" fallback message instead of a picker', () => {
      render(<ShippingOptionPicker options={[]} onSelect={vi.fn()} />);

      expect(screen.getByTestId('shipping-options-empty')).toBeInTheDocument();
      expect(
        screen.getByText(/shipping is not currently available for this address/i),
      ).toBeInTheDocument();
      expect(screen.getByText(/please contact support/i)).toBeInTheDocument();
      expect(screen.queryByRole('radio')).not.toBeInTheDocument();
    });

    it('renders a way to go back and try a different address', async () => {
      const onChangeAddress = vi.fn();
      const user = userEvent.setup();
      render(
        <ShippingOptionPicker options={[]} onSelect={vi.fn()} onChangeAddress={onChangeAddress} />,
      );

      await user.click(screen.getByRole('button', { name: /try a different address/i }));

      expect(onChangeAddress).toHaveBeenCalledOnce();
    });

    it('does not render the "try a different address" button when no handler is given', () => {
      render(<ShippingOptionPicker options={[]} onSelect={vi.fn()} />);

      expect(
        screen.queryByRole('button', { name: /try a different address/i }),
      ).not.toBeInTheDocument();
    });
  });

  // ── Request-level error (distinct from a successful empty result) ─────────
  describe('error state', () => {
    it('shows the error message instead of the empty-options fallback', () => {
      render(
        <ShippingOptionPicker
          options={[]}
          error="Could not load shipping options. Please try again."
          onSelect={vi.fn()}
        />,
      );

      expect(screen.getByRole('alert')).toHaveTextContent(
        'Could not load shipping options. Please try again.',
      );
      expect(screen.queryByTestId('shipping-options-empty')).not.toBeInTheDocument();
    });
  });
});
