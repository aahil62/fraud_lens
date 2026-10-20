// Display formatting. Formatters are built once: tables call these for every row.
const RUPEES = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});
const WHOLE_RUPEES = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});
const IST = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium",
  timeStyle: "medium",
  timeZone: "Asia/Kolkata",
});

export const channelName = (channel: string) =>
  ({ upi: "UPI", net_banking: "Net banking", card: "Cards", atm: "ATMs" })[channel] ?? channel;
export const money = (minor: number) => RUPEES.format(minor / 100);
/** Whole rupees without paise (₹48,000); paise shown only when present. */
export const rupees = (minor: number) => (minor % 100 ? RUPEES : WHOLE_RUPEES).format(minor / 100);
export const dateTime = (iso: string) => IST.format(new Date(iso));
export const human = (value: string) => value.replaceAll("_", " ");
