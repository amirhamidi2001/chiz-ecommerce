// src/utils/address.js
//
// Address helpers shared between the checkout picker and anywhere else
// that needs to render a saved address. Kept out of AddressPicker.jsx so
// that component file only exports a component (React Fast Refresh warns
// on mixed component/constant exports).
import { provinceLabel } from '../constants/provinces';

/**
 * Sentinel for the "Enter a new address" choice in the checkout picker.
 * Deliberately not `null` so callers can distinguish "user explicitly
 * chose to type a new address" from "nothing selected yet".
 */
export const NEW_ADDRESS = 'new';

/** One-line rendering of a saved address, e.g. "12 Valiasr St, Tehran, Tehran 1234567890". */
export const formatAddress = (addr) => {
  if (!addr) return '';
  return [
    [addr.address_line, addr.apartment].filter(Boolean).join(', '),
    addr.city,
    [provinceLabel(addr.province), addr.postal_code].filter(Boolean).join(' '),
  ]
    .filter(Boolean)
    .join(', ');
};
