// src/components/AddressPicker.jsx
import { NEW_ADDRESS, formatAddress } from '../utils/address';

/**
 * Lets a signed-in shopper reuse an address from their account address
 * book instead of retyping it, or opt into entering a new one.
 *
 * Renders NOTHING when there are no saved addresses — a picker offering
 * only "enter a new address" is pure noise, and the manual form the
 * caller already renders is the whole UI in that case.
 *
 * Props:
 *   addresses  {Array}  saved addresses from /dashboard/addresses/
 *   selectedId {number|'new'|null}  currently selected address id, or NEW_ADDRESS
 *   onSelect   {function} called with an address id (number) or NEW_ADDRESS
 *   loading    {boolean} show a skeleton while addresses are being fetched
 */
const AddressPicker = ({ addresses = [], selectedId, onSelect, loading = false }) => {
  if (loading) {
    return (
      <div className="p-5 border-b" data-testid="address-picker-loading">
        <div className="h-5 w-40 bg-gray-100 rounded animate-pulse mb-3" />
        <div className="h-16 bg-gray-100 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (!addresses.length) return null;

  const isSelected = (value) => String(selectedId) === String(value);

  return (
    <div className="p-5 border-b" data-testid="address-picker">
      <h4 className="text-sm font-semibold text-gray-700 mb-3">
        Use a saved address
      </h4>

      <div className="space-y-2">
        {addresses.map((addr) => (
          <label
            key={addr.id}
            className={`flex items-start gap-3 p-3 border rounded-xl cursor-pointer transition ${isSelected(addr.id)
              ? 'border-teal-500 bg-teal-50/50'
              : 'border-gray-200 hover:bg-gray-50'
              }`}
          >
            <input
              type="radio"
              name="saved_address"
              value={addr.id}
              checked={isSelected(addr.id)}
              onChange={() => onSelect(addr.id)}
              className="mt-1 w-4 h-4 accent-teal-600 flex-shrink-0"
            />
            <span className="text-sm leading-relaxed">
              <span className="font-semibold capitalize">{addr.label}</span>
              {addr.is_default && (
                <span className="ml-2 bg-teal-100 text-teal-700 text-xs px-2 py-0.5 rounded-full font-medium">
                  Default
                </span>
              )}
              <span className="block text-gray-700">{addr.full_name}</span>
              <span className="block text-gray-500">{formatAddress(addr)}</span>
            </span>
          </label>
        ))}

        <label
          className={`flex items-center gap-3 p-3 border rounded-xl cursor-pointer transition ${isSelected(NEW_ADDRESS)
            ? 'border-teal-500 bg-teal-50/50'
            : 'border-gray-200 hover:bg-gray-50'
            }`}
        >
          <input
            type="radio"
            name="saved_address"
            value={NEW_ADDRESS}
            checked={isSelected(NEW_ADDRESS)}
            onChange={() => onSelect(NEW_ADDRESS)}
            className="w-4 h-4 accent-teal-600 flex-shrink-0"
          />
          <span className="text-sm font-medium text-gray-700">
            Enter a new address
          </span>
        </label>
      </div>
    </div>
  );
};

export default AddressPicker;
