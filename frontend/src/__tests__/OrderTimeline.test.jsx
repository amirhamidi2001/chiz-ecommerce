/* global process */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import OrderTimeline from '../components/OrderTimeline';
import {
  ORDER_CANCELLED_MESSAGE_FA,
  ORDER_STATUS_LABELS_FA,
  ORDER_STEPS,
} from '../constants/orderStatus';

const active = () => ORDER_STEPS.map((s) => screen.getByTestId(`order-step-${s}`).dataset.active === 'true');

describe('OrderTimeline', () => {
  it.each([
    ['pending', [true, false, false, false]],
    ['processing', [true, true, false, false]],
    ['shipped', [true, true, true, false]],
    ['delivered', [true, true, true, true]],
  ])('%s highlights exactly the steps reached so far', (status, expected) => {
    render(<OrderTimeline status={status} />);
    expect(active()).toEqual(expected);
    expect(screen.getByTestId(`order-step-${status}`).dataset.current).toBe('true');
    expect(screen.queryByTestId('order-cancelled')).toBeNull();
  });

  it('shows a check on completed steps and the number on the rest', () => {
    render(<OrderTimeline status="shipped" />);
    expect(screen.getByTestId('order-step-pending').querySelector('.bi-check')).not.toBeNull();
    expect(screen.getByTestId('order-step-processing').querySelector('.bi-check')).not.toBeNull();
    // current + future steps show their number
    expect(screen.getByTestId('order-step-shipped')).toHaveTextContent('3');
    expect(screen.getByTestId('order-step-delivered')).toHaveTextContent('4');
  });

  it('marks every step done (checks) once delivered', () => {
    render(<OrderTimeline status="delivered" />);
    ORDER_STEPS.forEach((s) =>
      expect(screen.getByTestId(`order-step-${s}`).querySelector('.bi-check')).not.toBeNull(),
    );
  });

  it('colours a connector only when the step after it has been reached', () => {
    render(<OrderTimeline status="processing" />);
    expect(screen.getByTestId('order-connector-pending').className).toMatch(/bg-teal-600/);
    expect(screen.getByTestId('order-connector-processing').className).toMatch(/bg-gray-200/);
  });

  it('renders the Persian label under every step', () => {
    render(<OrderTimeline status="pending" />);
    ORDER_STEPS.forEach((s) => expect(screen.getByText(ORDER_STATUS_LABELS_FA[s])).toBeInTheDocument());
  });

  it('flags the current step for assistive tech', () => {
    render(<OrderTimeline status="processing" />);
    const current = document.querySelectorAll('[aria-current="step"]');
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveTextContent(ORDER_STATUS_LABELS_FA.processing);
  });

  it('renders cancelled as a distinct red state INSTEAD of the step sequence', () => {
    render(<OrderTimeline status="cancelled" />);
    const box = screen.getByTestId('order-cancelled');
    expect(box).toHaveTextContent(ORDER_CANCELLED_MESSAGE_FA);
    expect(box.className).toMatch(/text-red-700/);
    expect(screen.queryByTestId('order-timeline')).toBeNull();
    ORDER_STEPS.forEach((s) => expect(screen.queryByTestId(`order-step-${s}`)).toBeNull());
  });

  it('highlights nothing for an unknown status instead of guessing', () => {
    render(<OrderTimeline status="on_hold" />);
    expect(active()).toEqual([false, false, false, false]);
    expect(document.querySelector('[aria-current="step"]')).toBeNull();
  });
});

describe('order status labels', () => {
  // The labels must be the project's existing Persian catalog, not new wording.
  const po = readFileSync(
    // vitest runs from frontend/, and jsdom's import.meta.url is not a file: URL
    resolve(process.cwd(), '../backend/locale/fa/LC_MESSAGES/django.po'),
    'utf8',
  );
  const catalog = (msgid) => {
    const m = po.match(new RegExp(`msgid "${msgid}"\\nmsgstr "([^"]+)"`));
    return m && m[1];
  };

  it.each([
    ['pending', 'Pending'],
    ['processing', 'Processing'],
    ['shipped', 'Shipped'],
    ['delivered', 'Delivered'],
    ['cancelled', 'Cancelled'],
  ])('%s matches the django.po translation', (status, msgid) => {
    expect(catalog(msgid)).toBeTruthy();
    expect(ORDER_STATUS_LABELS_FA[status]).toBe(catalog(msgid));
  });
});
