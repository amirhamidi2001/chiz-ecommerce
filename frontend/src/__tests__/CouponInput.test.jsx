import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CouponInput from '../components/CouponInput';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const setup = (props = {}) => {
  const onApply = vi.fn().mockResolvedValue({ success: true });
  const onRemove = vi.fn().mockResolvedValue({ success: true });
  const utils = render(
    <CouponInput
      couponCode={null}
      couponDiscount="0"
      couponError={null}
      onApply={onApply}
      onRemove={onRemove}
      {...props}
    />,
  );
  return { onApply, onRemove, user: userEvent.setup(), ...utils };
};

const input = () => screen.getByPlaceholderText(/coupon code/i);
const applyBtn = () => screen.getByRole('button', { name: /apply coupon/i });

/** A promise whose resolution the test controls, to observe in-flight state. */
const deferred = () => {
  let resolve;
  const promise = new Promise((r) => {
    resolve = r;
  });
  return { promise, resolve };
};

beforeEach(() => vi.clearAllMocks());

// ═════════════════════════════════════════════════════════════════════════════
// Entry form (no coupon attached)
// ═════════════════════════════════════════════════════════════════════════════
describe('CouponInput — entry form', () => {
  it('shows a code input and an Apply Coupon button', () => {
    setup();
    expect(input()).toBeInTheDocument();
    expect(applyBtn()).toBeEnabled();
    expect(screen.queryByRole('button', { name: /remove/i })).not.toBeInTheDocument();
  });

  it('limits the code to the backend’s 32 characters', () => {
    setup();
    expect(input()).toHaveAttribute('maxLength', '32');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// Apply — success
// ═════════════════════════════════════════════════════════════════════════════
describe('CouponInput — apply success', () => {
  it('calls onApply with the trimmed code', async () => {
    const { onApply, user } = setup();

    await user.type(input(), '  SUMMER20  ');
    await user.click(applyBtn());

    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply).toHaveBeenCalledWith('SUMMER20');
  });

  it('clears the input and shows no error after a successful apply', async () => {
    const { user } = setup();

    await user.type(input(), 'SUMMER20');
    await user.click(applyBtn());

    await waitFor(() => expect(input()).toHaveValue(''));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('submits when Enter is pressed in the input', async () => {
    const { onApply, user } = setup();

    await user.type(input(), 'SUMMER20{Enter}');

    expect(onApply).toHaveBeenCalledWith('SUMMER20');
  });

  it('disables the form while the request is in flight and ignores a second submit', async () => {
    const pending = deferred();
    const onApply = vi.fn().mockReturnValue(pending.promise);
    const { user } = setup({ onApply });

    await user.type(input(), 'SUMMER20');
    await user.click(applyBtn());

    const busyBtn = screen.getByRole('button', { name: /applying/i });
    expect(busyBtn).toBeDisabled();
    expect(input()).toBeDisabled();
    await user.click(busyBtn);
    expect(onApply).toHaveBeenCalledTimes(1);

    pending.resolve({ success: true });
    await waitFor(() => expect(applyBtn()).toBeEnabled());
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// Apply — failure: the backend's specific message is shown verbatim
// ═════════════════════════════════════════════════════════════════════════════
describe('CouponInput — apply failure', () => {
  it.each([
    'Invalid coupon code.',
    'This coupon has expired.',
    'This coupon is not yet valid.',
    'This coupon is no longer active.',
    'This coupon requires a minimum order of 50.00.',
    'This coupon requires a minimum eligible order of 100.00.',
    'This coupon has reached its usage limit.',
    'You have already used this coupon.',
    'This coupon does not apply to any items in your cart.',
  ])('renders the backend message: "%s"', async (message) => {
    const onApply = vi.fn().mockResolvedValue({ success: false, message });
    const { user } = setup({ onApply });

    await user.type(input(), 'BADCODE');
    await user.click(applyBtn());

    expect(await screen.findByRole('alert')).toHaveTextContent(message);
    // Specific, not a generic fallback.
    expect(screen.queryByText(/could not apply coupon/i)).not.toBeInTheDocument();
  });

  it('keeps the typed code so a typo can be corrected', async () => {
    const onApply = vi.fn().mockResolvedValue({ success: false, message: 'Invalid coupon code.' });
    const { user } = setup({ onApply });

    await user.type(input(), 'SUMER20');
    await user.click(applyBtn());
    await screen.findByRole('alert');

    expect(input()).toHaveValue('SUMER20');
    expect(applyBtn()).toBeEnabled();
  });

  it('falls back to a generic message only when none is provided', async () => {
    const onApply = vi.fn().mockResolvedValue({ success: false });
    const { user } = setup({ onApply });

    await user.type(input(), 'X');
    await user.click(applyBtn());

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not apply coupon. Please try again.',
    );
  });

  it('clears the error as soon as the user edits the code', async () => {
    const onApply = vi.fn().mockResolvedValue({ success: false, message: 'Invalid coupon code.' });
    const { user } = setup({ onApply });

    await user.type(input(), 'X');
    await user.click(applyBtn());
    await screen.findByRole('alert');

    await user.type(input(), 'Y');

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it.each(['', '   '])('does not call onApply for an empty code (%j)', async (typed) => {
    const { onApply, user } = setup();

    if (typed) await user.type(input(), typed);
    await user.click(applyBtn());

    expect(onApply).not.toHaveBeenCalled();
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a coupon code.');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// Applied coupon
// ═════════════════════════════════════════════════════════════════════════════
describe('CouponInput — applied coupon', () => {
  const applied = { couponCode: 'SUMMER20', couponDiscount: '10.00' };

  it('shows the applied code and the discount instead of the entry form', () => {
    setup(applied);

    expect(screen.getByText('SUMMER20')).toBeInTheDocument();
    expect(screen.getByText(/you save \$10\.00/i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/coupon code/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /apply coupon/i })).not.toBeInTheDocument();
  });

  it('omits the savings text when the discount is zero', () => {
    setup({ couponCode: 'SUMMER20', couponDiscount: '0' });
    expect(screen.getByText('SUMMER20')).toBeInTheDocument();
    expect(screen.queryByText(/you save/i)).not.toBeInTheDocument();
  });

  it('calls onRemove when Remove is clicked', async () => {
    const { onRemove, user } = setup(applied);

    await user.click(screen.getByRole('button', { name: /remove coupon SUMMER20/i }));

    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it('disables Remove while removing', async () => {
    const pending = deferred();
    const onRemove = vi.fn().mockReturnValue(pending.promise);
    const { user } = setup({ ...applied, onRemove });

    await user.click(screen.getByRole('button', { name: /remove coupon SUMMER20/i }));

    expect(screen.getByRole('button', { name: /removing/i })).toBeDisabled();
    pending.resolve({ success: true });
    await waitFor(() => expect(screen.getByRole('button', { name: /remove coupon SUMMER20/i })).toBeEnabled());
  });

  it('shows the message and stays in the applied state when removal fails', async () => {
    const onRemove = vi.fn().mockResolvedValue({ success: false, message: 'Could not remove coupon.' });
    const { user } = setup({ ...applied, onRemove });

    await user.click(screen.getByRole('button', { name: /remove coupon SUMMER20/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not remove coupon.');
    expect(screen.getByText('SUMMER20')).toBeInTheDocument();
  });

  it('returns to the entry form once the cart no longer has a coupon', () => {
    const { rerender, onApply, onRemove } = setup(applied);
    expect(screen.queryByPlaceholderText(/coupon code/i)).not.toBeInTheDocument();

    rerender(
      <CouponInput
        couponCode={null}
        couponDiscount="0"
        couponError={null}
        onApply={onApply}
        onRemove={onRemove}
      />,
    );

    expect(input()).toBeInTheDocument();
    expect(applyBtn()).toBeEnabled();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// Attached coupon that has since become invalid (coupon_error)
// ═════════════════════════════════════════════════════════════════════════════
describe('CouponInput — attached coupon that is no longer valid', () => {
  const invalid = {
    couponCode: 'SUMMER20',
    couponDiscount: '0',
    couponError: 'This coupon has expired.',
  };

  it('shows the code, the backend’s reason, and that it isn’t reducing the total', () => {
    setup(invalid);

    expect(screen.getByText(/SUMMER20 can.t be applied/)).toBeInTheDocument();
    expect(screen.getByText('This coupon has expired.')).toBeInTheDocument();
    expect(screen.getByText(/isn.t reducing your total/i)).toBeInTheDocument();
  });

  it('does not present it as applied or show any savings', () => {
    setup({ ...invalid, couponDiscount: '10.00' });

    // The applied state's button ("Remove coupon SUMMER20") must not
    // appear — this state's button is the plain "Remove coupon" — nor any
    // savings.
    expect(
      screen.queryByRole('button', { name: /remove coupon SUMMER20/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/you save/i)).not.toBeInTheDocument();
  });

  it('offers Remove coupon, which calls onRemove', async () => {
    const { onRemove, user } = setup(invalid);

    await user.click(screen.getByRole('button', { name: /remove coupon/i }));

    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it('does not show the entry form until the bad coupon is removed', () => {
    setup(invalid);
    expect(screen.queryByPlaceholderText(/coupon code/i)).not.toBeInTheDocument();
  });

  it('shows the message when removing the invalid coupon fails', async () => {
    const onRemove = vi.fn().mockResolvedValue({ success: false, message: 'Could not remove coupon. Please try again.' });
    const { user } = setup({ ...invalid, onRemove });

    await user.click(screen.getByRole('button', { name: /remove coupon/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not remove coupon. Please try again.');
  });
});
