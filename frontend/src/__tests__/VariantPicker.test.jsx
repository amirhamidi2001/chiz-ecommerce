import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import VariantPicker from '../components/VariantPicker';
import { formatToman } from '../utils/money';

const ROSE = {
  id: 1, sku: 'SKU-ROSE', price: 100_000, effective_price: 100_000,
  color: { id: 1, name: 'Rose', hex_code: '#ff0066' }, volume_ml: 30, weight_g: null,
};
const NUDE = {
  id: 2, sku: 'SKU-NUDE', price: 125_000, effective_price: 125_000,
  color: { id: 2, name: 'Nude', hex_code: '#d2b48c' }, volume_ml: null, weight_g: null,
};

const renderPicker = (props = {}) => {
  const onSelect = vi.fn();
  render(
    <VariantPicker variants={[ROSE, NUDE]} selectedId={null} onSelect={onSelect} {...props} />,
  );
  return { onSelect };
};

describe('VariantPicker', () => {
  it('renders one radio per variant inside a labelled radiogroup', () => {
    renderPicker({ label: 'Choose a shade' });
    expect(screen.getByRole('radiogroup', { name: 'Choose a shade' })).toBeInTheDocument();
    expect(screen.getAllByRole('radio')).toHaveLength(2);
  });

  it('labels a variant with its colour and size, and shows its price', () => {
    renderPicker();
    const rose = screen.getByRole('radio', { name: /Rose · 30 ml/ });
    expect(rose).toHaveTextContent(formatToman(100_000));
    expect(screen.getByRole('radio', { name: /Nude/ })).toHaveTextContent(formatToman(125_000));
  });

  it('falls back to the SKU when a variant has no colour or size', () => {
    renderPicker({ variants: [{ id: 9, sku: 'PLAIN-1', price: 50_000, color: null }] });
    expect(screen.getByRole('radio', { name: /PLAIN-1/ })).toBeInTheDocument();
  });

  it('marks only the selected variant as checked', () => {
    renderPicker({ selectedId: 2 });
    expect(screen.getByRole('radio', { name: /Nude/ })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('radio', { name: /Rose/ })).toHaveAttribute('aria-checked', 'false');
  });

  it('reports the clicked variant id', async () => {
    const { onSelect } = renderPicker();
    await userEvent.click(screen.getByRole('radio', { name: /Nude/ }));
    expect(onSelect).toHaveBeenCalledWith(2);
  });

  it('shows the flash-sale price with the regular price struck through', () => {
    renderPicker({ variants: [{ ...ROSE, effective_price: 80_000 }] });
    const rose = screen.getByRole('radio', { name: /Rose/ });
    expect(rose).toHaveTextContent(formatToman(80_000));
    expect(rose).toHaveTextContent(formatToman(100_000));
    expect(screen.getByText(formatToman(100_000))).toHaveClass('line-through');
  });

  it('does not call onSelect when disabled', async () => {
    const { onSelect } = renderPicker({ disabled: true });
    await userEvent.click(screen.getByRole('radio', { name: /Rose/ }));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
