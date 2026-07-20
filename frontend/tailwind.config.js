/** @type {import("tailwindcss").Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#2563eb",
          hover: "#1d4ed8",
          subtle: "#1e3a8a",
          soft: "#dbeafe",
          text: "#bfdbfe",
          textLight: "#1d4ed8",
        },
        secondary: {
          DEFAULT: "#4b5563",
          hover: "#374151",
          soft: "#f3f4f6",
          text: "#d1d5db",
          textLight: "#374151",
        },
        success: {
          DEFAULT: "#16a34a",
          hover: "#15803d",
          subtle: "#14532d",
          soft: "#dcfce7",
          text: "#bbf7d0",
          textLight: "#166534",
        },
        warning: {
          DEFAULT: "#d97706",
          hover: "#b45309",
          subtle: "#713f12",
          soft: "#fef3c7",
          text: "#fde68a",
          textLight: "#92400e",
        },
        danger: {
          DEFAULT: "#dc2626",
          hover: "#b91c1c",
          subtle: "#7f1d1d",
          soft: "#fee2e2",
          text: "#fecaca",
          textLight: "#991b1b",
        },
        info: {
          DEFAULT: "#0284c7",
          hover: "#0369a1",
          subtle: "#0c4a6e",
          soft: "#e0f2fe",
          text: "#bae6fd",
          textLight: "#0369a1",
        },
        muted: {
          DEFAULT: "#6b7280",
          hover: "#4b5563",
          subtle: "#374151",
          soft: "#f9fafb",
          text: "#9ca3af",
          textLight: "#4b5563",
        },
        brand: {
          50: "#f0f9ff",
          100: "#e0f2fe",
          500: "#0ea5e9",
          600: "#0284c7",
          700: "#0369a1",
          900: "#0c4a6e",
        },
      },
    },
  },
  plugins: [],
};
