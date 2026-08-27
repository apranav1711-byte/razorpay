import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Activity, ArrowUpRight, ShieldCheck, Sparkles, WalletCards } from "lucide-react";
import { ScreenHeader, RiskBadge, formatInr } from "@/components/ScreenHeader";
import { riskSeries, transactions } from "@/lib/demo";

const kpis = [
  { label: "Transactions scored", value: "1,248", note: "+12.4% this week", icon: Activity, tone: "blue" },
  { label: "High-tier exposure", value: "₹3.21L", note: "19 transactions", icon: WalletCards, tone: "orange" },
  { label: "Disputes this month", value: "28", note: "6 awaiting review", icon: ShieldCheck, tone: "charcoal" },
  { label: "Evidence-recovered", value: "₹1.86L", note: "Human-reviewed only", icon: Sparkles, tone: "pink" },
];

export default function Overview() {
  return <div className="screen-shell">
    <ScreenHeader eyebrow="Merchant risk desk / live view" title="Good morning, Priya." />
    <section className="hand-note note-blue"><span>Model live</span><strong>Precision 32.4% · Recall 64.2%</strong><small>Held-out synthetic evaluation · calibrated model v1.0</small></section>
    <div className="kpi-grid">{kpis.map(({ label, value, note, icon: Icon, tone }) => <article className="sketch-card kpi-card" key={label}>
      <div className={`kpi-icon ${tone}`}><Icon size={18} /></div><p>{label}</p><strong>{value}</strong><span>{note}<ArrowUpRight size={14} /></span>
    </article>)}</div>
    <div className="overview-grid">
      <section className="sketch-card chart-card"><div className="card-heading"><div><p className="eyebrow">Seven-day signal</p><h2>Risk distribution</h2></div><div className="chart-legend"><span><i className="legend-low" />Low</span><span><i className="legend-medium" />Medium</span><span><i className="legend-high" />High</span></div></div>
        <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={riskSeries} margin={{ top: 12, right: 6, left: -22, bottom: 0 }}><defs><linearGradient id="lowFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#91E0BE" stopOpacity=".72" /><stop offset="100%" stopColor="#91E0BE" stopOpacity=".04" /></linearGradient></defs><CartesianGrid vertical={false} stroke="#D9D0C2" strokeDasharray="3 5" /><XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#7F7466", fontSize: 12 }} /><YAxis tickLine={false} axisLine={false} tick={{ fill: "#7F7466", fontSize: 11 }} /><Tooltip contentStyle={{ borderRadius: 15, border: "1px dashed #2F2B29", background: "#FFFCF4" }} /><Area isAnimationActive={false} type="monotone" dataKey="low" stackId="1" stroke="#3AAE83" fill="url(#lowFill)" strokeWidth={2} /><Area isAnimationActive={false} type="monotone" dataKey="medium" stackId="1" stroke="#F0A646" fill="#F7D78E" strokeWidth={2} /><Area isAnimationActive={false} type="monotone" dataKey="high" stackId="1" stroke="#E66C63" fill="#F2A59D" strokeWidth={2} /></AreaChart></ResponsiveContainer></div>
      </section>
      <aside className="sketch-card signal-card"><p className="eyebrow">Today’s margin note</p><h2>Why we flag</h2><div className="signal-list"><div><span className="signal-nbr">01</span><p><strong>Velocity</strong><small>High-risk signals cluster around transaction bursts.</small></p></div><div><span className="signal-nbr">02</span><p><strong>Cross-border mismatch</strong><small>IP / billing divergence needs a human check.</small></p></div><div><span className="signal-nbr">03</span><p><strong>Evidence gaps</strong><small>We surface missing proof; we never fill it in.</small></p></div></div></aside>
    </div>
    <section className="sketch-card table-card"><div className="card-heading"><div><p className="eyebrow">Requires attention</p><h2>Recent high-risk transactions</h2></div><a href="/risk-feed">See full risk feed <ArrowUpRight size={15} /></a></div><div className="data-table-wrap"><table className="data-table"><thead><tr><th>Transaction</th><th>Customer</th><th>Amount</th><th>Risk score</th><th>Top signals</th><th>Action</th></tr></thead><tbody>{transactions.filter(item => item.tier === "high").map(item => <tr key={item.transactionId}><td className="mono">{item.transactionId}</td><td>{item.customer}</td><td>{formatInr(item.amount)}</td><td><RiskBadge tier="high" /><strong className="score-number">{Math.round(item.riskScore * 100)}%</strong></td><td><div className="factor-chips">{item.factors.slice(0, 3).map(factor => <span key={factor.feature}>{factor.displayName}</span>)}</div></td><td><button className="text-action">{item.action}</button></td></tr>)}</tbody></table></div></section>
  </div>;
}
