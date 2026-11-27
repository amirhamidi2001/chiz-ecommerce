// src/constants/orderStatus.js
//
// Customer-facing Persian labels for Order.Status (backend/order/models.py).
// The wording is NOT invented here: it is the project's existing Persian catalog
// (backend/locale/fa/LC_MESSAGES/django.po, Task 14.1.1.4), the same strings the
// backend serves for these statuses ("ارسال شد", not "ارسال شده"). A test
// (__tests__/OrderTimeline.test.jsx) pins this table to the .po file so the two
// cannot drift apart silently.

// The normal progression. `cancelled` is deliberately NOT a step: it is a
// terminal state that replaces the progression instead of sitting on it.
export const ORDER_STEPS = ['pending', 'processing', 'shipped', 'delivered'];

export const ORDER_STATUS_LABELS_FA = {
  pending: 'در انتظار',
  processing: 'در حال پردازش',
  shipped: 'ارسال شد',
  delivered: 'تحویل داده شد',
  cancelled: 'لغو شده',
};

export const ORDER_CANCELLED_MESSAGE_FA = 'این سفارش لغو شده است';
