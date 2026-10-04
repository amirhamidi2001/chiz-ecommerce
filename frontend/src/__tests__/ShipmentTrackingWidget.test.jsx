import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ShipmentTrackingWidget from '../components/ShipmentTrackingWidget';

const baseShipment = (overrides = {}) => ({
  carrier_name: 'Iran Post',
  tracking_number: 'TRK123456',
  status: 'pending',
  status_display: 'Pending Pickup',
  last_tracked_at: null,
  ...overrides,
});

describe('ShipmentTrackingWidget', () => {
  // ── Not yet shipped ─────────────────────────────────────────────────────────
  describe('when shipment is null', () => {
    it('renders the "not yet shipped" state, not an empty/broken section', () => {
      render(<ShipmentTrackingWidget shipment={null} />);

      expect(screen.getByTestId('shipment-not-shipped')).toBeInTheDocument();
      expect(screen.getByText(/not yet shipped/i)).toBeInTheDocument();
      expect(screen.queryByTestId('shipment-tracking')).not.toBeInTheDocument();
      expect(screen.queryByTestId('shipment-failed')).not.toBeInTheDocument();
    });

    it('renders the same state when shipment is undefined', () => {
      render(<ShipmentTrackingWidget />);

      expect(screen.getByTestId('shipment-not-shipped')).toBeInTheDocument();
    });
  });

  // ── Each non-terminal status value ──────────────────────────────────────────
  describe.each([
    { status: 'pending', label: 'Pending Pickup', activeSteps: ['pending'] },
    {
      status: 'in_transit',
      label: 'In Transit',
      activeSteps: ['pending', 'in_transit'],
    },
    {
      status: 'out_for_delivery',
      label: 'Out for Delivery',
      activeSteps: ['pending', 'in_transit', 'out_for_delivery'],
    },
    {
      status: 'delivered',
      label: 'Delivered',
      activeSteps: ['pending', 'in_transit', 'out_for_delivery', 'delivered'],
    },
  ])('when status is $status', ({ status, label, activeSteps }) => {
    const shipment = baseShipment({ status, status_display: label });

    it('renders carrier name, status label, and tracking number', () => {
      render(<ShipmentTrackingWidget shipment={shipment} />);

      expect(screen.getByTestId('shipment-tracking')).toBeInTheDocument();
      expect(screen.getByText('Iran Post')).toBeInTheDocument();
      // The status label may legitimately appear twice (the status badge
      // and, for some statuses, the matching step's own label) — assert
      // presence, not a single unique match.
      expect(screen.getAllByText(label).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/TRK123456/)).toBeInTheDocument();
    });

    it('renders the step indicator with the correct steps marked active', () => {
      render(<ShipmentTrackingWidget shipment={shipment} />);

      const allSteps = ['pending', 'in_transit', 'out_for_delivery', 'delivered'];
      for (const stepKey of allSteps) {
        const stepEl = screen.getByTestId(`step-${stepKey}`);
        const expectedActive = String(activeSteps.includes(stepKey));
        expect(stepEl).toHaveAttribute('data-active', expectedActive);
      }
    });

    it('does not render the failed-state banner', () => {
      render(<ShipmentTrackingWidget shipment={shipment} />);

      expect(screen.queryByTestId('shipment-failed')).not.toBeInTheDocument();
    });
  });

  // ── Failed status gets distinct treatment ───────────────────────────────────
  describe('when status is failed', () => {
    const shipment = baseShipment({ status: 'failed', status_display: 'Failed' });

    it('renders the failed banner instead of the step indicator', () => {
      render(<ShipmentTrackingWidget shipment={shipment} />);

      expect(screen.getByTestId('shipment-failed')).toBeInTheDocument();
      expect(screen.getByText('Failed')).toBeInTheDocument();
      expect(screen.getByText(/Iran Post/)).toBeInTheDocument();
      expect(screen.getByText(/TRK123456/)).toBeInTheDocument();
      expect(screen.queryByTestId('shipment-steps')).not.toBeInTheDocument();
      expect(screen.queryByTestId('shipment-tracking')).not.toBeInTheDocument();
    });
  });

  // ── Carrier tracking links ───────────────────────────────────────────────────
  describe('carrier tracking links', () => {
    it('links the tracking number to the carrier site for Iran Post', () => {
      render(<ShipmentTrackingWidget shipment={baseShipment({ carrier_name: 'Iran Post' })} />);

      const link = screen.getByRole('link', { name: /TRK123456/ });
      expect(link).toHaveAttribute('href', 'https://tracking.post.ir/');
      expect(link).toHaveAttribute('target', '_blank');
    });

    it('links the tracking number to the carrier site for Tipax', () => {
      render(
        <ShipmentTrackingWidget
          shipment={baseShipment({ carrier_name: 'Tipax', tracking_number: 'TPX999' })}
        />,
      );

      const link = screen.getByRole('link', { name: /TPX999/ });
      expect(link).toHaveAttribute('href', 'https://www.tipax.ir/');
    });

    it('shows the tracking number as plain text (no link) for SnapBox', () => {
      render(
        <ShipmentTrackingWidget
          shipment={baseShipment({ carrier_name: 'SnapBox', tracking_number: 'SB123' })}
        />,
      );

      expect(screen.getByText(/SB123/)).toBeInTheDocument();
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('shows the tracking number as plain text (no link) for AloPeyk', () => {
      render(
        <ShipmentTrackingWidget
          shipment={baseShipment({ carrier_name: 'AloPeyk', tracking_number: 'AP456' })}
        />,
      );

      expect(screen.getByText(/AP456/)).toBeInTheDocument();
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('is case-insensitive when matching the carrier name', () => {
      render(<ShipmentTrackingWidget shipment={baseShipment({ carrier_name: 'iran post' })} />);

      expect(screen.getByRole('link')).toHaveAttribute('href', 'https://tracking.post.ir/');
    });
  });

  // ── Edge cases ───────────────────────────────────────────────────────────────
  describe('edge cases', () => {
    it('shows a placeholder when tracking_number is blank (not yet booked with the carrier)', () => {
      render(<ShipmentTrackingWidget shipment={baseShipment({ tracking_number: '' })} />);

      expect(screen.getByText(/tracking number not yet assigned/i)).toBeInTheDocument();
      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('shows "last updated" when last_tracked_at is present', () => {
      render(
        <ShipmentTrackingWidget
          shipment={baseShipment({ last_tracked_at: '2026-01-15T10:30:00Z' })}
        />,
      );

      expect(screen.getByText(/last updated/i)).toBeInTheDocument();
    });

    it('omits "last updated" when last_tracked_at is null', () => {
      render(<ShipmentTrackingWidget shipment={baseShipment({ last_tracked_at: null })} />);

      expect(screen.queryByText(/last updated/i)).not.toBeInTheDocument();
    });

    it('defaults to the pending step when status is unrecognized', () => {
      render(<ShipmentTrackingWidget shipment={baseShipment({ status: 'something_weird' })} />);

      expect(screen.getByTestId('step-pending')).toHaveAttribute('data-active', 'true');
      expect(screen.getByTestId('step-in_transit')).toHaveAttribute('data-active', 'false');
    });
  });
});
