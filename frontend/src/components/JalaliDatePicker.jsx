// src/components/JalaliDatePicker.jsx  (Task 14.2.1.4)
//
// A controlled date(-time) picker that is used and looks like a Jalali (Solar
// Hijri) calendar, while its EXTERNAL interface stays Gregorian — exactly what
// <input type="datetime-local"> / <input type="date"> speak:
//
//   value      "YYYY-MM-DDTHH:mm" (withTime, the default) or "YYYY-MM-DD", or "" for empty
//   onChange   called with a string in that same shape
//
// so a form wires it up like any input and never knows a Jalali conversion
// exists. All conversion happens in here, in calendar days (utils/jalaliCalendar.js),
// so no browser time zone can move the day. The time of day is passed through
// untouched: whatever zone the form already interprets "datetime-local" values in
// (the browser's, for the admin coupon form) it still does.
//
// No date-picker library exists in this project, and none of the Jalali ones are
// maintained and correct, so this is a small custom calendar grid
// (Saturday-first, month/year selects, optional time of day).

import { useEffect, useId, useMemo, useRef, useState } from 'react';
import {
  JALALI_MONTH_NAMES,
  JALALI_WEEKDAY_LABELS,
  buildMonthGrid,
  formatJalaliParts,
  gregorianToJalali,
  jalaliToGregorian,
  todayJalali,
} from '../utils/jalaliCalendar';

const VALUE_RE = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/;
const DEFAULT_TIME = '00:00';
const pad2 = (n) => String(n).padStart(2, '0');

/** "2030-01-01T10:00" -> { gregorian: {year, month, day}, time: "10:00" } | null (empty / unusable). */
function parseValue(value) {
  const m = typeof value === 'string' ? VALUE_RE.exec(value) : null;
  if (!m) return null;
  const [year, month, day] = [m[1], m[2], m[3]].map(Number);
  const check = new Date(Date.UTC(year, month - 1, day));
  if (check.getUTCMonth() !== month - 1 || check.getUTCDate() !== day) return null; // e.g. 2026-02-31
  return { gregorian: { year, month, day }, time: m[4] ? `${m[4]}:${m[5]}` : DEFAULT_TIME };
}

const toValue = ({ year, month, day }, time, withTime) =>
  `${year}-${pad2(month)}-${pad2(day)}${withTime ? `T${time}` : ''}`;

const selectCls =
  'border border-gray-200 rounded-lg px-2 py-1 text-sm bg-white focus:outline-none focus:border-teal-500';
const navBtnCls =
  'w-8 h-8 rounded-lg text-gray-600 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-teal-500';

const JalaliDatePicker = ({
  id,
  value,
  onChange,
  hasError = false,
  disabled = false,
  withTime = true,
  placeholder = 'Select a date',
}) => {
  const autoId = useId();
  const triggerId = id ?? autoId;
  const rootRef = useRef(null);
  const triggerRef = useRef(null);

  const parsed = useMemo(() => parseValue(value), [value]);
  const selected = useMemo(() => (parsed ? gregorianToJalali(parsed.gregorian) : null), [parsed]);
  const time = parsed?.time ?? DEFAULT_TIME;

  const [open, setOpen] = useState(false);
  const [view, setView] = useState(() => selected ?? todayJalali()); // { year, month } being shown
  const today = useMemo(() => todayJalali(), []);

  // Close on Escape (focus back to the field) and on a click outside.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    const onPointer = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onPointer);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onPointer);
    };
  }, [open]);

  const toggle = () => {
    if (disabled) return;
    if (!open) {
      const start = selected ?? todayJalali();
      setView({ year: start.year, month: start.month });
    }
    setOpen((o) => !o);
  };

  const weeks = useMemo(() => buildMonthGrid(view.year, view.month), [view.year, view.month]);

  const years = useMemo(() => {
    const set = new Set(Array.from({ length: 31 }, (_, i) => today.year - 5 + i)); // 5 back, 25 ahead
    set.add(view.year);
    if (selected) set.add(selected.year);
    return [...set].sort((a, b) => a - b);
  }, [today.year, view.year, selected]);

  const shiftMonth = (delta) =>
    setView(({ year, month }) => {
      const index = year * 12 + (month - 1) + delta;
      return { year: Math.floor(index / 12), month: (index % 12) + 1 };
    });

  const pickDay = (day) => {
    const gregorian = jalaliToGregorian({ year: view.year, month: view.month, day });
    if (gregorian) onChange(toValue(gregorian, time, withTime));
    if (!withTime) {
      setOpen(false);
      triggerRef.current?.focus();
    }
  };

  const changeTime = (e) => {
    if (!parsed || !e.target.value) return; // needs a day first; ignore a cleared time
    onChange(toValue(parsed.gregorian, e.target.value, withTime));
  };

  const label = selected
    ? `${formatJalaliParts(selected)}${withTime ? ` ${time}` : ''}`
    : null;

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        id={triggerId}
        type="button"
        disabled={disabled}
        aria-haspopup="true"
        aria-expanded={open}
        onClick={toggle}
        className={`w-full flex items-center justify-between gap-2 border rounded-xl px-3 py-2.5 text-sm text-start focus:outline-none focus:border-teal-500 transition disabled:opacity-60 ${
          hasError ? 'border-red-400 bg-red-50' : 'border-gray-200 bg-white'
        }`}
      >
        <span className={label ? 'text-gray-800' : 'text-gray-400'}>{label ?? placeholder}</span>
        <i className="bi bi-calendar3 text-gray-400" aria-hidden="true"></i>
      </button>

      {open && (
        <div
          role="group"
          aria-label="Jalali date picker"
          className="absolute z-50 mt-1 w-72 bg-white border border-gray-200 rounded-xl shadow-lg p-3"
        >
          <div className="flex items-center gap-1 mb-2">
            <button type="button" className={navBtnCls} aria-label="Previous month" onClick={() => shiftMonth(-1)}>
              <i className="bi bi-chevron-left icon-directional" aria-hidden="true"></i>
            </button>
            <select
              aria-label="Month"
              className={`${selectCls} flex-1`}
              value={view.month}
              onChange={(e) => setView((v) => ({ ...v, month: Number(e.target.value) }))}
            >
              {JALALI_MONTH_NAMES.map((name, i) => (
                <option key={name} value={i + 1}>{name}</option>
              ))}
            </select>
            <select
              aria-label="Year"
              className={selectCls}
              value={view.year}
              onChange={(e) => setView((v) => ({ ...v, year: Number(e.target.value) }))}
            >
              {years.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <button type="button" className={navBtnCls} aria-label="Next month" onClick={() => shiftMonth(1)}>
              <i className="bi bi-chevron-right icon-directional" aria-hidden="true"></i>
            </button>
          </div>

          <div className="grid grid-cols-7 text-center text-[11px] font-semibold text-gray-400 mb-1">
            {JALALI_WEEKDAY_LABELS.map((d) => (
              <span key={d} className={d === 'Fr' ? 'text-red-400' : ''}>{d}</span>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-y-1">
            {weeks.flat().map((day, i) => {
              if (day === null) return <span key={`blank-${i}`} />;
              const isSelected =
                selected && selected.year === view.year && selected.month === view.month && selected.day === day;
              const isToday = today.year === view.year && today.month === view.month && today.day === day;
              return (
                <button
                  key={day}
                  type="button"
                  aria-label={`${day} ${JALALI_MONTH_NAMES[view.month - 1]} ${view.year}`}
                  aria-pressed={Boolean(isSelected)}
                  onClick={() => pickDay(day)}
                  className={`h-8 text-sm rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 ${
                    isSelected
                      ? 'bg-teal-600 text-white font-semibold'
                      : isToday
                        ? 'border border-teal-500 text-teal-700 hover:bg-teal-50'
                        : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {day}
                </button>
              );
            })}
          </div>

          {withTime && (
            <div className="flex items-center gap-2 mt-3">
              <label htmlFor={`${triggerId}-time`} className="text-xs font-semibold text-gray-600">
                Time
              </label>
              <input
                id={`${triggerId}-time`}
                type="time"
                value={parsed ? time : ''}
                disabled={!parsed}
                onChange={changeTime}
                className={`${selectCls} flex-1`}
              />
            </div>
          )}

          <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-100">
            <span className="text-[11px] text-gray-400" data-testid="gregorian-hint">
              {parsed ? `Gregorian: ${toValue(parsed.gregorian, time, withTime).replace('T', ' ')}` : 'No date selected'}
            </span>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                triggerRef.current?.focus();
              }}
              className="text-xs font-semibold text-teal-700 hover:text-teal-900"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default JalaliDatePicker;
