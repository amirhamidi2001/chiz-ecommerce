// src/components/OrderTimeline.jsx
//
// Step indicator for Order.Status: pending -> processing -> shipped -> delivered.
// `cancelled` is a terminal state, so it REPLACES the progression with a red
// notice instead of being forced onto the linear sequence.
//
// Layout note: the page is RTL (<html dir="rtl">), and a flex row follows the
// writing direction, so step 1 sits on the right and the connectors read
// right-to-left with no extra CSS. Labels are Persian, from constants/orderStatus.js.
import {
  ORDER_CANCELLED_MESSAGE_FA,
  ORDER_STATUS_LABELS_FA,
  ORDER_STEPS,
} from '../constants/orderStatus';

const OrderTimeline = ({ status }) => {
  if (status === 'cancelled') {
    return (
      <div
        role="status"
        data-testid="order-cancelled"
        className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 flex items-center gap-2 font-semibold text-sm"
      >
        <i className="bi bi-x-circle-fill" aria-hidden="true"></i>
        <span>{ORDER_CANCELLED_MESSAGE_FA}</span>
      </div>
    );
  }

  // An unknown status (e.g. a future one) highlights nothing rather than guessing.
  const currentIndex = ORDER_STEPS.indexOf(status);
  const isDelivered = status === 'delivered';

  return (
    <ol className="flex items-start" data-testid="order-timeline" aria-label="وضعیت سفارش">
      {ORDER_STEPS.map((step, i) => {
        const reached = i <= currentIndex;
        // The final step has nothing after it, so once delivered every step is "done".
        const done = i < currentIndex || (isDelivered && i === currentIndex);
        const isCurrent = i === currentIndex;
        return (
          <li
            key={step}
            className="flex items-start flex-1 last:flex-none"
            aria-current={isCurrent ? 'step' : undefined}
          >
            <div className="flex flex-col items-center">
              <div
                data-testid={`order-step-${step}`}
                data-active={reached}
                data-current={isCurrent}
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                  reached ? 'bg-teal-600 text-white' : 'bg-gray-200 text-gray-400'
                } ${isCurrent && !isDelivered ? 'ring-4 ring-teal-100' : ''}`}
              >
                {done ? <i className="bi bi-check" aria-hidden="true"></i> : i + 1}
              </div>
              <span
                className={`text-xs mt-1.5 text-center whitespace-nowrap ${
                  reached ? 'text-teal-700 font-medium' : 'text-gray-400'
                }`}
              >
                {ORDER_STATUS_LABELS_FA[step]}
              </span>
            </div>
            {i < ORDER_STEPS.length - 1 && (
              <div
                data-testid={`order-connector-${step}`}
                className={`flex-1 h-1 mt-3.5 mx-1 rounded ${
                  i < currentIndex ? 'bg-teal-600' : 'bg-gray-200'
                }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
};

export default OrderTimeline;
