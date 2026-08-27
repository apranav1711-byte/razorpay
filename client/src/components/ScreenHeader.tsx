import { Bell, Search } from "lucide-react";

export function ScreenHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: React.ReactNode }) {
  return <header className="screen-header">
    <div>
      <p className="eyebrow">{eyebrow}</p>
      <h1 className="marker-heading">{title}</h1>
    </div>
    <div className="header-actions">
      {children}
      <button className="icon-button" aria-label="Search dashboard"><Search size={18} /></button>
      <button className="icon-button has-notification" aria-label="View alerts"><Bell size={18} /></button>
    </div>
  </header>;
}

export function RiskBadge({ tier }: { tier: "low" | "medium" | "high" }) {
  return <span className={`risk-badge risk-${tier}`}><span className="badge-dot" />{tier} risk</span>;
}

export const formatInr = (cents: number) => `₹${(cents / 100).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
