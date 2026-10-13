import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import VariantPicker from '../components/VariantPicker';

const ROSE = {
  id: 1, sku: 'SKU-ROSE', price: '10.00', effective_price: '10.00',
  color: { id: 1, name: 'Rose', hex_code: '#ff0066' }, volume_ml: 30, weight_g: null,
};
const NUDE = {
  id: 2, sku: 'SKU-NUDE', price: '12.50', effective_price: '12.50',
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
    expect(rose).toHaveTextContent('$10.00');
    expect(screen.getByRole('radio', { name: /Nude/ })).toHaveTextContent('$12.50');
  });

  it('falls back to the SKU when a variant has no colour or size', () => {
    renderPicker({ variants: [{ id: 9, sku: 'PLAIN-1', price: '5.00', color: null }] });
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
    renderPicker({ variants: [{ ...ROSE, effective_price: '8.00' }] });
    const rose = screen.getByRole('radio', { name: /Rose/ });
    expect(rose).toHaveTextContent('$8.00');
    expect(rose).toHaveTextContent('$10.00');
    expect(screen.getByText('$10.00')).toHaveClass('line-through');
  });

  it('does not call onSelect when disabled', async () => {
    const { onSelect } = renderPicker({ disabled: true });
    await userEvent.click(screen.getByRole('radio', { name: /Rose/ }));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
