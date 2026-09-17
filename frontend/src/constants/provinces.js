// src/constants/provinces.js
//
// The 31 official provinces (ostan) of Iran — the single source of truth
// for every province <select> in this app (account address book AND
// checkout). Values MUST match backend `dashboard.models.IranProvince`
// exactly; they are sent to the API verbatim.
//
// WHY A HARDCODED LIST RATHER THAN DRF'S OPTIONS ENDPOINT:
// DRF does expose these dynamically — an OPTIONS request to
// /api/dashboard/addresses/ returns actions.POST.province.choices with
// all 31 entries (verified against the running server). BUT that
// endpoint is IsAuthenticated, and returns 401 to anonymous users, so
// it cannot populate the province dropdown on a page an unauthenticated
// visitor can reach. A single shared constant works everywhere, needs
// no extra request before the form can render, and — critically — the
// usual drift risk of hand-copying a backend enum is covered by an
// automated parity test: backend/dashboard/tests/test_province_sync.py
// reads THIS FILE and fails if it diverges from IranProvince.choices.
// So if you edit either list without the other, CI tells you.
export const IRAN_PROVINCES = [
  { value: 'alborz', label: 'Alborz' },
  { value: 'ardabil', label: 'Ardabil' },
  { value: 'bushehr', label: 'Bushehr' },
  { value: 'chaharmahal_and_bakhtiari', label: 'Chaharmahal and Bakhtiari' },
  { value: 'east_azerbaijan', label: 'East Azerbaijan' },
  { value: 'fars', label: 'Fars' },
  { value: 'gilan', label: 'Gilan' },
  { value: 'golestan', label: 'Golestan' },
  { value: 'hamadan', label: 'Hamadan' },
  { value: 'hormozgan', label: 'Hormozgan' },
  { value: 'ilam', label: 'Ilam' },
  { value: 'isfahan', label: 'Isfahan' },
  { value: 'kerman', label: 'Kerman' },
  { value: 'kermanshah', label: 'Kermanshah' },
  { value: 'khuzestan', label: 'Khuzestan' },
  { value: 'kohgiluyeh_and_boyer_ahmad', label: 'Kohgiluyeh and Boyer-Ahmad' },
  { value: 'kurdistan', label: 'Kurdistan' },
  { value: 'lorestan', label: 'Lorestan' },
  { value: 'markazi', label: 'Markazi' },
  { value: 'mazandaran', label: 'Mazandaran' },
  { value: 'north_khorasan', label: 'North Khorasan' },
  { value: 'qazvin', label: 'Qazvin' },
  { value: 'qom', label: 'Qom' },
  { value: 'khorasan_razavi', label: 'Khorasan Razavi' },
  { value: 'semnan', label: 'Semnan' },
  { value: 'sistan_and_baluchestan', label: 'Sistan and Baluchestan' },
  { value: 'south_khorasan', label: 'South Khorasan' },
  { value: 'tehran', label: 'Tehran' },
  { value: 'west_azerbaijan', label: 'West Azerbaijan' },
  { value: 'yazd', label: 'Yazd' },
  { value: 'zanjan', label: 'Zanjan' },
];

export const IRAN_PROVINCE_VALUES = IRAN_PROVINCES.map((p) => p.value);

/** Human-readable label for a stored province value (falls back to the raw value). */
export const provinceLabel = (value) =>
  IRAN_PROVINCES.find((p) => p.value === value)?.label ?? value ?? '';

/** Iran's postal code format: exactly 10 digits. Mirrors the backend's RegexValidator. */
export const IRAN_POSTAL_CODE_RE = /^\d{10}$/;

export const isValidPostalCode = (value) => IRAN_POSTAL_CODE_RE.test(String(value ?? '').trim());
