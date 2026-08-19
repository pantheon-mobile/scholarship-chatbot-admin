function jstDateParts(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(date);
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? "";
  return { year: value("year"), month: value("month"), day: value("day") };
}

export function initialDashboardPeriod(date = new Date()) {
  const { year, month, day } = jstDateParts(date);
  return { from: `${year}-${month}-01`, to: `${year}-${month}-${day}` };
}
