/**
 * StatCard — KPI card used in the admin dashboard overview.
 *
 * Props:
 *   title     string
 *   value     string | number
 *   change    number   (% change, positive/negative)
 *   icon      string   Bootstrap icon class (e.g. "bi-cart")
 *   color     "teal" | "blue" | "amber" | "violet" | "red" | "pink"
 *   loading   boolean
 *   prefix    string   (e.g. "$")
 *   suffix    string   (e.g. "%")
 */
const PALETTES = {
  teal: { wrap: "bg-teal-50", icon: "text-teal-600", badge: "bg-teal-100 text-teal-700" },
  blue: { wrap: "bg-blue-50", icon: "text-blue-600", badge: "bg-blue-100 text-blue-700" },
  amber: { wrap: "bg-amber-50", icon: "text-amber-600", badge: "bg-amber-100 text-amber-700" },
  violet: { wrap: "bg-violet-50", icon: "text-violet-600", badge: "bg-violet-100 text-violet-700" },
  red: { wrap: "bg-red-50", icon: "text-red-600", badge: "bg-red-100 text-red-700" },
  pink: { wrap: "bg-pink-50", icon: "text-pink-600", badge: "bg-pink-100 text-pink-700" },
};

const StatCard = ({
  title = "",
  value = "",
  change = null,
  icon = "bi-graph-up",
  color = "teal",
  loading = false,
  prefix = "",
  suffix = "",
  onClick,
}) => {
  const p = PALETTES[color] || PALETTES.teal;
  const isUp = change > 0;
  const isFlat = change === 0 || change === null;

  return (
    <div
      className={`bg-white border border-gray-100 rounded-2xl p-5 shadow-sm ${onClick ? "cursor-pointer hover:shadow-md transition" : ""
        }`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-4">
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${p.wrap}`}>
          <i className={`bi ${icon} text-xl ${p.icon}`}></i>
        </div>
        {change !== null && !loading && (
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded-full flex items-center gap-1 ${isFlat
                ? "bg-gray-100 text-gray-500"
                : isUp
                  ? "bg-green-100 text-green-700"
                  : "bg-red-100 text-red-700"
              }`}
          >
            <i className={`bi ${isFlat ? "bi-dash" : isUp ? "bi-arrow-up-short" : "bi-arrow-down-short"} text-sm`}></i>
            {Math.abs(change)}%
          </span>
        )}
      </div>

      {loading ? (
        <>
          <div className="h-8 bg-gray-100 rounded-lg w-24 animate-pulse mb-2" />
          <div className="h-4 bg-gray-100 rounded w-32 animate-pulse" />
        </>
      ) : (
        <>
          <div className="text-2xl font-bold text-gray-800">
            {prefix}{value}{suffix}
          </div>
          <div className="text-sm text-gray-500 mt-1">{title}</div>
          {change !== null && (
            <p className="text-xs text-gray-400 mt-1">
              {isFlat ? "No change" : `${isUp ? "Up" : "Down"} ${Math.abs(change)}%`} vs last period
            </p>
          )}
        </>
      )}
    </div>
  );
};

export default StatCard;
