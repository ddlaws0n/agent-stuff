module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  safelist: ["bg-green-500", "bg-amber-500", "bg-red-500"],
  theme: {
    extend: {
      colors: { brand: { 500: "#3b82f6" } },
    },
  },
};
