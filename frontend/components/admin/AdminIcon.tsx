import { SVGProps } from "react";

export type AdminIconName =
  | "university" | "menu" | "dashboard" | "database" | "help" | "list"
  | "chat" | "chart" | "back" | "download" | "plus" | "edit" | "trash" | "grip" | "search" | "upload" | "close";

type AdminIconProps = SVGProps<SVGSVGElement> & { name: AdminIconName; size?: number };

export function AdminIcon({ name, size = 24, ...props }: AdminIconProps) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.9, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const paths: Record<AdminIconName, React.ReactNode> = {
    university: <><path d="M3 8.5 12 3l9 5.5H3Z"/><path d="M5 20.5h14M3.5 22h17M6.5 8.5v12m3.7-12v12m3.6-12v12m3.7-12v12"/></>,
    menu: <path d="M3.5 6h17M3.5 12h17M3.5 18h17"/>,
    dashboard: <><circle cx="12" cy="12" r="9"/><circle cx="6.7" cy="10" r="1" fill="currentColor" stroke="none"/><circle cx="8.7" cy="6.8" r="1" fill="currentColor" stroke="none"/><circle cx="12.4" cy="5.6" r="1" fill="currentColor" stroke="none"/><circle cx="16.2" cy="7.2" r="1" fill="currentColor" stroke="none"/><path d="m11 16.5 4.8-7.1"/><circle cx="11" cy="16.5" r="1.25" fill="currentColor" stroke="none"/></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></>,
    help: <><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.6 2.6 0 1 1 3.4 2.5c-.7.3-.9.9-.9 1.7M12 17.2h.01"/></>,
    list: <><path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4" cy="6" r="1" fill="currentColor" stroke="none"/><circle cx="4" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="4" cy="18" r="1" fill="currentColor" stroke="none"/></>,
    chat: <><path d="M21 11.2a8.2 8.2 0 0 1-8.2 8.2H8L3 22l1.5-4.7A8.6 8.6 0 1 1 21 11.2Z"/><circle cx="8" cy="11.5" r=".8" fill="currentColor" stroke="none"/><circle cx="12" cy="11.5" r=".8" fill="currentColor" stroke="none"/><circle cx="16" cy="11.5" r=".8" fill="currentColor" stroke="none"/></>,
    chart: <><path d="M4 20v-7h4v7M10 20V8h4v12M16 20V4h4v16M2.5 20.5h19"/></>,
    back: <><path d="m14 6-6 6 6 6"/></>,
    download: <><path d="M12 3v12m-4-4 4 4 4-4M4 18v3h16v-3"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    edit: <><path d="m4 20 4.2-1 10.9-10.9a2.1 2.1 0 0 0-3-3L5.2 16 4 20ZM14.5 6.5l3 3"/></>,
    trash: <><path d="M4 7h16M9 7V4h6v3m3 0-1 14H7L6 7m4 4v6m4-6v6"/></>,
    grip: <><circle cx="9" cy="5" r="1" fill="currentColor" stroke="none"/><circle cx="15" cy="5" r="1" fill="currentColor" stroke="none"/><circle cx="9" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="15" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="9" cy="19" r="1" fill="currentColor" stroke="none"/><circle cx="15" cy="19" r="1" fill="currentColor" stroke="none"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 4.5 4.5"/></>,
    upload: <><path d="M7 18H5.5a3.5 3.5 0 0 1-.5-7A6.8 6.8 0 0 1 18.2 9a4.5 4.5 0 0 1 .3 9H17"/><path d="M12 19V9m-4 4 4-4 4 4"/></>,
    close: <><circle cx="12" cy="12" r="9"/><path d="m9 9 6 6m0-6-6 6"/></>,
  };

  return <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" {...common} {...props}>{paths[name]}</svg>;
}
