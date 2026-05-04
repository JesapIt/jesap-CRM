/**
 * Table sort utilities — handles text, number, date, percent.
 * Reads `data-sort-type` from <th data-sort-key="..."> elements.
 *
 * Supported types:
 *   - "text"    (default): case-insensitive lexical
 *   - "number" : strips currency/symbols, parses as float (es. "€ 1.234,56" → 1234.56)
 *   - "date"   : parses DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY → timestamp
 *   - "percent": "85%" → 85
 *
 * Empty cells ("-", "", "None") sink to the bottom regardless of direction.
 */
(function (global) {
  "use strict";

  const SortUtils = {
    /** Parse date string in DD/MM/YYYY, YYYY-MM-DD, or DD-MM-YYYY format. */
    parseDate(text) {
      if (!text) return null;
      text = String(text).trim();
      if (!text || text === "-" || text === "None") return null;
      let m;
      // DD/MM/YYYY
      if ((m = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/))) {
        return new Date(+m[3], +m[2] - 1, +m[1]).getTime();
      }
      // YYYY-MM-DD (ISO)
      if ((m = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/))) {
        return new Date(+m[1], +m[2] - 1, +m[3]).getTime();
      }
      // DD-MM-YYYY
      if ((m = text.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/))) {
        return new Date(+m[3], +m[2] - 1, +m[1]).getTime();
      }
      // DD/MM/YY (2-digit year, assume 2000s)
      if ((m = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2})$/))) {
        return new Date(2000 + (+m[3]), +m[2] - 1, +m[1]).getTime();
      }
      return null;
    },

    /** Parse number from text — strips €, $, %, spaces, handles IT format (1.234,56). */
    parseNumber(text) {
      if (!text) return null;
      const raw = String(text).trim();
      if (!raw || raw === "-" || raw === "None") return null;
      // Strip everything except digits, dot, comma, minus
      let cleaned = raw.replace(/[^0-9.,-]+/g, "");
      // IT format "1.234,56" → "1234.56"
      if (cleaned.includes(",") && cleaned.includes(".")) {
        cleaned = cleaned.replace(/\./g, "").replace(",", ".");
      } else if (cleaned.includes(",")) {
        cleaned = cleaned.replace(",", ".");
      }
      const n = parseFloat(cleaned);
      return isNaN(n) ? null : n;
    },

    /** Get comparable value from text, based on type. */
    parseValue(text, type) {
      if (text == null) return null;
      const trimmed = String(text).trim();
      if (!trimmed || trimmed === "-" || trimmed === "None") return null;
      switch (type) {
        case "date":
          return this.parseDate(trimmed);
        case "number":
        case "percent":
          return this.parseNumber(trimmed);
        case "text":
        default:
          return trimmed.toLowerCase();
      }
    },

    /**
     * Compare two parsed values respecting direction.
     * Empty values (null) ALWAYS sink to bottom regardless of direction.
     */
    compare(a, b, dir) {
      // Both empty
      if (a === null && b === null) return 0;
      // One empty: empty always last
      if (a === null) return 1;
      if (b === null) return -1;
      const sign = dir === "asc" ? 1 : -1;
      if (a < b) return -1 * sign;
      if (a > b) return 1 * sign;
      return 0;
    },

    /**
     * Read sort type from the <th> for a given sort key.
     * Falls back to "text" if not declared.
     */
    typeForKey(key) {
      const th = document.querySelector(`th[data-sort-key="${CSS.escape(key)}"]`);
      return (th && th.dataset.sortType) || "text";
    },
  };

  global.SortUtils = SortUtils;
})(window);
