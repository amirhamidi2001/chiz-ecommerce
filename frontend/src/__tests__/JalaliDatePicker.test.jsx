/* global process */
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import JalaliDatePicker from '../components/JalaliDatePicker';
import { JALALI_MONTH_NAMES } from '../utils/jalaliCalendar';
import { KNOWN_PAIRS } from '../utils/tests/jalaliReferenceDates';

// "Today" is pinned so the year list (5 years back, 25 ahead of today's Jalali year,
// 1405 on this date) cannot drift as the real calendar moves on.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 10, 2, 12, 0));
});
afterEach(() => vi.useRealTimers());

/** Controlled wrapper, the way a form wires it; records every emitted value. */
const Harness = ({ initial = '', onValue = () => {}, ...props }) => {
  const [value, setValue] = useState(initial);
  return (
    <>
      <label htmlFor="when">When</label>
      <JalaliDatePicker
        id="when"
        value={value}
        onChange={(v) => {
          onValue(v);
          setValue(v);
        }}
        {...props}
      />
    </>
  );
};

const trigger = () => screen.getByLabelText('When');
const picker = () => screen.getByRole('group', { name: /jalali date picker/i });

const open = async (user) => {
  await user.click(trigger());
  return picker();
};

/** Choose a Jalali year/month in the open picker, then click the day. */
const pickJalali = async (user, [year, month, day]) => {
  const p = picker();
  await user.selectOptions(within(p).getByLabelText('Year'), String(year));
  await user.selectOptions(within(p).getByLabelText('Month'), String(month));
  await user.click(within(p).getByRole('button', { name: `${day} ${JALALI_MONTH_NAMES[month - 1]} ${year}` }));
};

const jalaliParts = (text) => text.split('/').map(Number);

describe('JalaliDatePicker — showing an existing Gregorian value in Jalali', () => {
  it.each(KNOWN_PAIRS)('%s is shown as %s (%s)', (gregorian, jalali) => {
    render(<Harness initial={`${gregorian}T10:30`} />);
    expect(trigger()).toHaveTextContent(`${jalali} 10:30`);
  });

  it('opens on the stored month with the stored day highlighted (not a reset picker)', async () => {
    const user = userEvent.setup();
    render(<Harness initial="2024-02-11T08:00" />); // 22 Bahman 1402
    const p = await open(user);
    expect(within(p).getByLabelText('Year')).toHaveValue('1402');
    expect(within(p).getByLabelText('Month')).toHaveValue('11');
    expect(within(p).getByRole('button', { name: '22 Bahman 1402' })).toHaveAttribute('aria-pressed', 'true');
    expect(within(p).getByRole('button', { name: '23 Bahman 1402' })).toHaveAttribute('aria-pressed', 'false');
    expect(within(p).getByTestId('gregorian-hint')).toHaveTextContent('Gregorian: 2024-02-11 08:00');
  });

  it('shows the placeholder for an empty or unusable value', () => {
    const { rerender } = render(<JalaliDatePicker id="a" value="" onChange={() => {}} placeholder="Pick one" />);
    expect(screen.getByText('Pick one')).toBeInTheDocument();
    rerender(<JalaliDatePicker id="a" value="not a date" onChange={() => {}} placeholder="Pick one" />);
    expect(screen.getByText('Pick one')).toBeInTheDocument();
    rerender(<JalaliDatePicker id="a" value="2026-02-31T10:00" onChange={() => {}} placeholder="Pick one" />);
    expect(screen.getByText('Pick one')).toBeInTheDocument(); // 31 Feb does not exist
  });

  it('accepts a date-only value', () => {
    render(<Harness initial="2026-03-21" withTime={false} />);
    expect(trigger()).toHaveTextContent('1405/01/01');
  });
});

describe('JalaliDatePicker — picking a Jalali date emits the Gregorian one', () => {
  // Only the pairs whose Jalali year the year list offers (1400-1430 on the pinned
  // date); the 1357 and 1379 pairs are covered by the display tests above.
  const reachable = KNOWN_PAIRS.filter(([, jalali]) => jalaliParts(jalali)[0] >= 1400).map(
    ([gregorian, jalali, why]) => ({ gregorian, jalali, why }),
  );

  it.each(reachable)('picking $jalali emits $gregorian ($why)', async ({ gregorian, jalali }) => {
    const user = userEvent.setup();
    const onValue = vi.fn();
    render(<Harness onValue={onValue} />);
    await open(user);
    await pickJalali(user, jalaliParts(jalali));

    expect(onValue).toHaveBeenLastCalledWith(`${gregorian}T00:00`);
    expect(trigger()).toHaveTextContent(`${jalali} 00:00`);
  });

  it('keeps the time of day already set when a different day is picked', async () => {
    const user = userEvent.setup();
    const onValue = vi.fn();
    render(<Harness initial="2026-03-21T14:45" onValue={onValue} />);
    await open(user);
    await user.click(within(picker()).getByRole('button', { name: '2 Farvardin 1405' }));
    expect(onValue).toHaveBeenLastCalledWith('2026-03-22T14:45');
  });

  it('changing the time keeps the day, and emits the new time', async () => {
    const user = userEvent.setup();
    const onValue = vi.fn();
    render(<Harness initial="2026-03-21T14:45" onValue={onValue} />);
    await open(user);
    fireEvent.change(within(picker()).getByLabelText('Time'), { target: { value: '23:59' } });
    expect(onValue).toHaveBeenLastCalledWith('2026-03-21T23:59');
    expect(trigger()).toHaveTextContent('1405/01/01 23:59');
  });

  it('emits a date-only value, and closes, when withTime is off', async () => {
    const user = userEvent.setup();
    const onValue = vi.fn();
    render(<Harness withTime={false} onValue={onValue} />);
    await open(user);
    await pickJalali(user, [1405, 1, 1]);
    expect(onValue).toHaveBeenLastCalledWith('2026-03-21');
    expect(screen.queryByRole('group', { name: /jalali date picker/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Time')).not.toBeInTheDocument();
  });

  it('does not depend on the browser time zone', async () => {
    const original = process.env.TZ;
    try {
      for (const zone of ['America/Los_Angeles', 'Asia/Tehran', 'Pacific/Auckland']) {
        process.env.TZ = zone;
        const user = userEvent.setup();
        const onValue = vi.fn();
        const { unmount } = render(<Harness initial="2024-02-11T00:00" onValue={onValue} />);
        expect(trigger()).toHaveTextContent('1402/11/22 00:00'); // display
        await open(user);
        await user.click(within(picker()).getByRole('button', { name: '23 Bahman 1402' }));
        expect(onValue).toHaveBeenLastCalledWith('2024-02-12T00:00'); // pick
        unmount();
      }
    } finally {
      if (original === undefined) delete process.env.TZ;
      else process.env.TZ = original;
    }
  });
});

describe('JalaliDatePicker — calendar behaviour', () => {
  it('has 30 days in Esfand of a leap year (1403) and 29 in a common year (1404)', async () => {
    const user = userEvent.setup();
    render(<Harness initial="2025-03-20T00:00" />); // 30 Esfand 1403
    const p = await open(user);
    expect(within(p).getByRole('button', { name: '30 Esfand 1403' })).toBeInTheDocument();
    await user.selectOptions(within(p).getByLabelText('Year'), '1404');
    expect(within(p).getByRole('button', { name: '29 Esfand 1404' })).toBeInTheDocument();
    expect(within(p).queryByRole('button', { name: '30 Esfand 1404' })).not.toBeInTheDocument();
  });

  it('previous/next month cross the year boundary', async () => {
    const user = userEvent.setup();
    render(<Harness initial="2026-03-21T00:00" />); // Farvardin 1405
    const p = await open(user);
    await user.click(within(p).getByRole('button', { name: 'Previous month' }));
    expect(within(p).getByLabelText('Month')).toHaveValue('12');
    expect(within(p).getByLabelText('Year')).toHaveValue('1404');
    await user.click(within(p).getByRole('button', { name: 'Next month' }));
    expect(within(p).getByLabelText('Month')).toHaveValue('1');
    expect(within(p).getByLabelText('Year')).toHaveValue('1405');
  });

  it('mirrors its previous/next month arrows in RTL', async () => {
    const user = userEvent.setup();
    render(<Harness initial="2026-03-21T00:00" />);
    const p = await open(user);
    expect(within(p).getByRole('button', { name: 'Previous month' }).querySelector('i')).toHaveClass(
      'bi-chevron-left', 'icon-directional',
    );
    expect(within(p).getByRole('button', { name: 'Next month' }).querySelector('i')).toHaveClass(
      'bi-chevron-right', 'icon-directional',
    );
  });

  it('opens on the current Jalali month when empty', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const p = await open(user);
    expect(within(p).getByLabelText('Year')).toHaveValue('1405');
    expect(within(p).getByLabelText('Month')).toHaveValue('8'); // 2 Nov 2026 = 11 Aban 1405
  });

  it('keeps the year list reachable for an old stored date', async () => {
    const user = userEvent.setup();
    render(<Harness initial="1979-02-11T00:00" />);
    const p = await open(user);
    expect(within(p).getByLabelText('Year')).toHaveValue('1357');
  });

  it('the time field is disabled until a day is chosen, and emits nothing', async () => {
    const user = userEvent.setup();
    const onValue = vi.fn();
    render(<Harness onValue={onValue} />);
    const p = await open(user);
    expect(within(p).getByLabelText('Time')).toBeDisabled();
    expect(onValue).not.toHaveBeenCalled();
  });

  it('opening and closing without picking emits nothing', async () => {
    const user = userEvent.setup();
    const onValue = vi.fn();
    render(<Harness initial="2026-03-21T10:00" onValue={onValue} />);
    await open(user);
    await user.click(within(picker()).getByRole('button', { name: 'Done' }));
    expect(onValue).not.toHaveBeenCalled();
  });

  it('closes on Escape (focus back on the field) and on an outside click', async () => {
    const user = userEvent.setup();
    render(<Harness initial="2026-03-21T10:00" />);
    await open(user);
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('group', { name: /jalali date picker/i })).not.toBeInTheDocument();
    expect(trigger()).toHaveFocus();

    await open(user);
    await user.click(document.body);
    expect(screen.queryByRole('group', { name: /jalali date picker/i })).not.toBeInTheDocument();
  });

  it('a disabled picker cannot be opened', async () => {
    const user = userEvent.setup();
    render(<Harness disabled />);
    await user.click(trigger());
    expect(screen.queryByRole('group', { name: /jalali date picker/i })).not.toBeInTheDocument();
  });

  it('is reachable through its <label>', () => {
    render(<Harness />);
    expect(screen.getByLabelText('When')).toBe(trigger());
  });
});
