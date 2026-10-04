// src/components/ShipmentTrackingWidget.jsx
//
// Task 7.2.2.3: shows shipment tracking status on the customer-facing
// order detail view (OrdersTab.jsx's OrderDetailModal). Renders a step
// indicator (Pending -> In Transit -> Out for Delivery -> Delivered), a
// distinct treatment for Failed, carrier + tracking number, and a
// "not yet shipped" state when order.shipment is null.
//
// CARRIER TRACKING LINKS — researched before building this, not assumed:
// does any of the four carriers (Tasks 7.2.1.2-7.2.1.5) have a public
// "enter your tracking number" webpage whose URL accepts the number as a
// query parameter/URL segment, so a direct, pre-filled deep link could be
// constructed? Findings: NONE of the four do.
//   - Iran Post (tracking.post.ir) and Tipax (www.tipax.ir) each have a
//     real, public consumer tracking webpage, but every source describes
//     typing the code into a form on that page by hand — no confirmed
//     query-string/URL-segment pattern exists that pre-fills the lookup.
//   - SnapBox and AloPeyk are on-demand courier apps (see their provider
//     files' own research): tracking happens live in their own app or
//     business panel during an active delivery, not via a persistent
//     public "look up by code" webpage at all.
// Given that, this deliberately does NOT fabricate a deep-link URL that
// embeds the tracking number for any carrier — that would be guessing at
// a URL pattern that was actively checked and found not to exist. Where a
// real tracking website exists at all (Post, Tipax), this links to that
// site's general tracking page — the customer still pastes the code in
// themselves — and the tracking number is always ALSO shown as plain,
// copyable text so there's something to paste. Where no public tracking
// site exists (SnapBox, AloPeyk), only the plain tracking number is shown.
const CARRIER_TRACKING_PAGES = {
  'iran post': 'https://tracking.post.ir/',
  tipax: 'https://www.tipax.ir/',
};

const getCarrierTrackingUrl = (carrierName) =>
  CARRIER_TRACKING_PAGES[(carrierName || '').trim().toLowerCase()] ?? null;

const STEPS = [
  { key: 'pending', label: 'Pending' },
  { key: 'in_transit', label: 'In Transit' },
  { key: 'out_for_delivery', label: 'Out for Delivery' },
  { key: 'delivered', label: 'Delivered' },
];

const STEP_INDEX = { pending: 0, in_transit: 1, out_for_delivery: 2, delivered: 3 };

const ShipmentTrackingWidget = ({ shipment }) => {
  if (!shipment) {
    return (
      <div
        className="bg-gray-50 border border-gray-200 rounded-xl p-4 flex items-center gap-2 text-sm text-gray-500"
        data-testid="shipment-not-shipped"
      >
        <i className="bi bi-box-seam"></i>
        <span>Not yet shipped</span>
      </div>
    );
  }

  const { carrier_name, tracking_number, status, status_display, last_tracked_at } = shipment;

  if (status === 'failed') {
    return (
      <div
        className="bg-red-50 border border-red-200 rounded-xl p-4"
        data-testid="shipment-failed"
      >
        <p className="text-sm font-semibold text-red-700 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle"></i>
          {status_display}
        </p>
        <p className="text-xs text-red-600 mt-1">
          {carrier_name}
          {tracking_number && ` — Tracking #: ${tracking_number}`}
        </p>
      </div>
    );
  }

  const currentStepIndex = STEP_INDEX[status] ?? 0;
  const trackingUrl = getCarrierTrackingUrl(carrier_name);

  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4" data-testid="shipment-tracking">
      <div className="flex justify-between items-start gap-3 mb-4">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-800">{carrier_name}</p>
          {tracking_number ? (
            trackingUrl ? (
              <a
                href={trackingUrl}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-teal-600 hover:underline break-all"
              >
                Tracking #: {tracking_number}
              </a>
            ) : (
              <p className="text-xs text-gray-500 break-all">Tracking #: {tracking_number}</p>
            )
          ) : (
            <p className="text-xs text-gray-400">Tracking number not yet assigned</p>
          )}
        </div>
        <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-2.5 py-1 rounded-full whitespace-nowrap">
          {status_display}
        </span>
      </div>

      {/* Step indicator: Pending -> In Transit -> Out for Delivery -> Delivered */}
      <div className="flex items-center" data-testid="shipment-steps">
        {STEPS.map((step, idx) => (
          <div key={step.key} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center">
              <div
                data-testid={`step-${step.key}`}
                data-active={idx <= currentStepIndex}
                className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
                  idx <= currentStepIndex ? 'bg-teal-600 text-white' : 'bg-gray-200 text-gray-400'
                }`}
              >
                {idx < currentStepIndex ? <i className="bi bi-check"></i> : idx + 1}
              </div>
              <span
                className={`text-[10px] mt-1 text-center whitespace-nowrap ${
                  idx <= currentStepIndex ? 'text-teal-700 font-medium' : 'text-gray-400'
                }`}
              >
                {step.label}
              </span>
            </div>
            {idx < STEPS.length - 1 && (
              <div
                className={`flex-1 h-0.5 mx-1 ${idx < currentStepIndex ? 'bg-teal-600' : 'bg-gray-200'}`}
              />
            )}
          </div>
        ))}
      </div>

      {last_tracked_at && (
        <p className="text-[11px] text-gray-400 mt-3">
          Last updated {new Date(last_tracked_at).toLocaleString()}
        </p>
      )}
    </div>
  );
};

export default ShipmentTrackingWidget;
