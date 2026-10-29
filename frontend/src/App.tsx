import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight,
  Bell, Boxes, CalendarDays, Check, ChevronDown, CircleHelp, Clock3,
  Download, LayoutDashboard, Leaf, Menu, Package, Search, Settings2,
  ShieldCheck, ShoppingBasket, Sparkles, TrendingDown, X
} from "lucide-react";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip,
  XAxis, YAxis, BarChart, Bar
} from "recharts";

type Item = {
  id: number; name: string; category: string; quantity: number;
  unit: string; expiry: string; days: number; status: "Healthy" | "Low stock" | "Expiring" | "Critical";
  value: number;
};

const initialItems: Item[] = [
  { id: 1, name: "Fresh milk", category: "Dairy", quantity: 18, unit: "cartons", expiry: "Today", days: 0, status: "Critical", value: 1620 },
  { id: 2, name: "Romaine lettuce", category: "Produce", quantity: 12, unit: "heads", expiry: "Tomorrow", days: 1, status: "Expiring", value: 720 },
  { id: 3, name: "Chicken breast", category: "Meat", quantity: 24, unit: "kg", expiry: "Oct 31", days: 2, status: "Expiring", value: 4320 },
  { id: 4, name: "Sourdough bread", category: "Bakery", quantity: 6, unit: "loaves", expiry: "Oct 31", days: 2, status: "Low stock", value: 540 },
  { id: 5, name: "Cherry tomatoes", category: "Produce", quantity: 32, unit: "boxes", expiry: "Nov 02", days: 4, status: "Healthy", value: 2560 },
  { id: 6, name: "Greek yogurt", category: "Dairy", quantity: 20, unit: "cups", expiry: "Nov 04", days: 6, status: "Healthy", value: 1800 },
];

const trend = [
  { day: "Oct 23", waste: 3200, saved: 1800 },
  { day: "Oct 24", waste: 2800, saved: 2100 },
  { day: "Oct 25", waste: 3500, saved: 2400 },
  { day: "Oct 26", waste: 2300, saved: 2700 },
  { day: "Oct 27", waste: 2600, saved: 3100 },
  { day: "Oct 28", waste: 1900, saved: 3500 },
  { day: "Oct 29", waste: 1600, saved: 3900 },
];

const wasteByCategory = [
  { category: "Produce", amount: 4200 },
  { category: "Dairy", amount: 2800 },
  { category: "Bakery", amount: 1900 },
  { category: "Meat", amount: 1400 },
  { category: "Other", amount: 900 },
];

const peso = (n: number) => "₱" + n.toLocaleString("en-PH");
const navItems = [
  { label: "Overview", icon: LayoutDashboard },
  { label: "Inventory", icon: Boxes },
  { label: "Expiry watch", icon: Clock3 },
  { label: "Waste analytics", icon: TrendingDown },
  { label: "Recommendations", icon: Sparkles },
];

function App() {
  const [page, setPage] = useState("Overview");
  const [items, setItems] = useState(initialItems);
  const [dataMode, setDataMode] = useState<"loading" | "live" | "demo">("loading");

  useEffect(() => {
    let cancelled = false;

    async function loadInventory() {
      try {
        const response = await fetch("http://127.0.0.1:8000/api/inventory");
        if (!response.ok) {
          throw new Error(`Inventory API returned HTTP ${response.status}`);
        }

        const records: Array<{
          id: number;
          name: string;
          category: string;
          quantity: number;
          unit: string;
          expiry_date: string | null;
          unit_cost: number;
          reorder_level: number;
          stock_value?: number;
        }> = await response.json();

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const liveItems: Item[] = records.map((record) => {
          const expiryDate = record.expiry_date
            ? new Date(`${record.expiry_date}T00:00:00`)
            : null;

          const days = expiryDate
            ? Math.round((expiryDate.getTime() - today.getTime()) / 86400000)
            : 9999;

          let status: Item["status"];
          if (days < 0) status = "Critical";
          else if (days === 0) status = "Critical";
          else if (days <= 2) status = "Expiring";
          else if (record.quantity <= record.reorder_level) status = "Low stock";
          else status = "Healthy";

          let expiry = "Not set";
          if (expiryDate) {
            expiry = days === 0
              ? "Today"
              : days === 1
                ? "Tomorrow"
                : expiryDate.toLocaleDateString("en-PH", {
                    month: "short",
                    day: "2-digit"
                  });
          }

          return {
            id: record.id,
            name: record.name,
            category: record.category,
            quantity: record.quantity,
            unit: record.unit,
            expiry,
            days,
            status,
            value: Number(record.stock_value ?? record.quantity * record.unit_cost)
          };
        });

        if (!cancelled) {
          setItems(liveItems);
          setDataMode("live");
        }
      } catch (error) {
        console.error("HarvestGuard inventory API connection failed:", error);
        if (!cancelled) setDataMode("demo");
      }
    }

    void loadInventory();
    return () => {
      cancelled = true;
    };
  }, []);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All items");
  const [notice, setNotice] = useState("");
  const [mobileNav, setMobileNav] = useState(false);

  const visibleItems = useMemo(() => items.filter((item) => {
    const matchesQuery = `${item.name} ${item.category}`.toLowerCase().includes(query.toLowerCase());
    const matchesFilter = filter === "All items" ||
      (filter === "At risk" && ["Critical", "Expiring"].includes(item.status)) ||
      (filter === "Low stock" && item.status === "Low stock");
    const matchesPage = page !== "Expiry watch" || item.days <= 2;
    return matchesQuery && matchesFilter && matchesPage;
  }), [items, query, filter, page]);

  const acknowledge = (id: number) => {
    setItems(current => current.map(item => item.id === id && item.status === "Critical"
      ? { ...item, status: "Expiring" } : item));
    setNotice("Alert reviewed. The item remains on the expiry watch list until action is taken.");
  };

  const exportInventory = () => {
    const header = "Item,Category,Quantity,Unit,Expiry,Status,Value PHP";
    const rows = items.map(item => [
      `"${item.name}"`, item.category, item.quantity, item.unit,
      item.expiry, item.status, item.value
    ].join(","));
    const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = "harvestguard-inventory-demo.csv"; link.click();
    URL.revokeObjectURL(url);
    setNotice("Demo inventory CSV exported.");
  };

  const inventoryPage = page === "Inventory" || page === "Expiry watch";
  const pageTitle = page === "Overview" ? "Good morning, team" : page;
  const pageSubtitle = page === "Overview"
    ? "Here’s what’s happening with your inventory today."
    : "Review your stock and take action with confidence.";

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Leaf size={23} strokeWidth={2.5} /></div>
          <div><strong>harvestguard<span>AI</span></strong><small>SMART FOOD OPERATIONS</small></div>
          <button className="mobile-close icon-button" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X /></button>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <button className="workspace-picker">
          <div className="workspace-avatar">G</div>
          <span><strong>Green Table Café</strong><small>Business workspace</small></span>
          <ChevronDown size={16} />
        </button>
        <div className="nav-label">MENU</div>
        <nav className="nav-list">
          {navItems.map(({ label, icon: Icon }) => (
            <button key={label} className={`nav-item ${page === label ? "active" : ""}`}
              onClick={() => { setPage(label); setMobileNav(false); setNotice(""); }}>
              <Icon size={18} /><span>{label}</span>
              {label === "Expiry watch" && <span className="nav-count">3</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-spacer" />
        <div className="impact-card">
          <div className="impact-icon"><Leaf size={18} /></div>
          <span className="impact-eyebrow">YOUR IMPACT THIS MONTH</span>
          <strong>18.4 <small>kg</small></strong>
          <p>food waste avoided</p>
          <div className="impact-progress"><span /></div>
          <small className="impact-note">73% of your monthly goal</small>
        </div>
        <button className="nav-item bottom-nav" onClick={() => setPage("Settings")}><Settings2 size={18} /><span>Settings</span></button>
        <div className="profile">
          <div className="profile-avatar">GT</div>
          <div><strong>Green Table Team</strong><small>Administrator</small></div>
          <ChevronDown size={16} />
        </div>
      </aside>

      {mobileNav && <button className="mobile-scrim" aria-label="Close menu" onClick={() => setMobileNav(false)} />}

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">
            <button className="mobile-menu icon-button" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu /></button>
            <span>Workspace</span><span className="crumb-slash">/</span><strong>{page}</strong>
          </div>
          <div className="top-actions">
            <div className="demo-pill">
              <span /> {dataMode === "live" ? "LIVE API" : dataMode === "loading" ? "CONNECTING" : "DEMO DATA"}
            </div>
            <button className="icon-button notification-button" aria-label="Notifications" onClick={() => setNotice("You have 3 inventory items that need attention.")}><Bell size={19} /><i /></button>
            <div className="top-divider" />
            <div className="today"><CalendarDays size={16} /><span>Oct 29, 2026</span></div>
          </div>
        </header>

        <div className="page-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow"><span className="eyebrow-dot" /> THURSDAY, OCTOBER 29, 2026</div>
              <h1>{pageTitle}{page === "Overview" && <span className="wave"> ✳</span>}</h1>
              <p>{pageSubtitle}</p>
            </div>
            <div className="heading-actions">
              <button className="button button-secondary" onClick={exportInventory}><Download size={16} /> Export report</button>
              <button className="button button-primary" onClick={() => { setPage("Inventory"); setNotice("Demo mode: inventory records are sample data. Database-backed editing will be connected in the next build stage."); }}><Package size={16} /> View inventory</button>
            </div>
          </div>

          {notice && <div className="notice" role="status"><ShieldCheck size={17} /><span>{notice}</span><button onClick={() => setNotice("")} aria-label="Dismiss notice"><X size={16} /></button></div>}

          {page === "Recommendations" ? (
            <section className="recommendations-page">
              <div className="section-heading"><div><h2>Recommended next actions</h2><p>Prioritized from the sample inventory’s expiry and stock signals.</p></div></div>
              <div className="recommendation-grid">
                <Recommendation icon={<AlertTriangle />} priority="HIGH PRIORITY" title="Use fresh milk today" description="18 cartons expire today. Prioritize menu items that use milk, or review safe donation options." impact="₱1,620 inventory at risk" />
                <Recommendation icon={<Clock3 />} priority="ACT TODAY" title="Prepare a lettuce special" description="12 heads of romaine lettuce expire tomorrow. Consider a limited-time salad or soup special." impact="₱720 inventory at risk" />
                <Recommendation icon={<ShoppingBasket />} priority="RESTOCK REVIEW" title="Check sourdough reorder" description="Only 6 loaves remain. Compare expected demand before placing your next order." impact="Low-stock signal" />
              </div>
              <p className="demo-disclaimer">These are rule-based demo suggestions, not verified forecasts. Always check food safety guidance and actual stock before acting.</p>
            </section>
          ) : page === "Waste analytics" ? (
            <>
              <div className="section-heading"><div><h2>Waste performance</h2><p>Sample weekly figures in Philippine pesos.</p></div></div>
              <div className="chart-grid">
                <section className="panel chart-panel"><div className="panel-heading"><div><h3>Waste cost by category</h3><p>Demo data · Last 7 days</p></div></div><div className="bar-chart"><ResponsiveContainer width="100%" height={300}><BarChart data={wasteByCategory} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#edf1ed" /><XAxis dataKey="category" tickLine={false} axisLine={false} tick={{ fill: "#758278", fontSize: 12 }} /><YAxis tickLine={false} axisLine={false} tick={{ fill: "#758278", fontSize: 12 }} tickFormatter={(v: number) => `₱${v / 1000}k`} /><Tooltip formatter={(v) => peso(Number(v))} /><Bar dataKey="amount" fill="#27865d" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div></section>
                <section className="panel chart-panel"><div className="panel-heading"><div><h3>Waste reduction focus</h3><p>What the demo data suggests</p></div></div><div className="focus-list">{wasteByCategory.slice(0, 4).map((item, i) => <div className="focus-row" key={item.category}><span className={`focus-number focus-${i}`}>{i + 1}</span><div className="focus-main"><strong>{item.category}</strong><div className="mini-track"><span style={{ width: `${item.amount / 4200 * 100}%` }} /></div></div><b>{peso(item.amount)}</b></div>)}</div></section>
              </div>
            </>
          ) : page === "Settings" ? (
            <section className="panel settings-panel"><div className="panel-heading"><div><h3>Workspace settings</h3><p>Demo workspace configuration</p></div></div><p><strong>Workspace:</strong> Green Table Café</p><p><strong>Currency:</strong> PHP (₱)</p><p><strong>Data mode:</strong> Synthetic sample data</p><p><strong>Backend:</strong> Not connected yet</p><div className="notice"><CircleHelp size={17} />Settings are illustrative. Authentication and persistent preferences are planned for later stages.</div></section>
          ) : (
            <>
              <div className="metric-grid">
                <Metric title="Inventory value" value={peso(items.reduce((sum, item) => sum + item.value, 0))} change="Across tracked stock" icon={<Boxes size={19} />} tone="green" trend="up" />
                <Metric title="Items expiring soon" value={String(items.filter(i => i.days <= 2).length)} change="Within the next 3 days" icon={<Clock3 size={19} />} tone="amber" trend="down" />
                <Metric title="Waste cost this week" value="₱11,200" change="↓ 18% vs. last week" icon={<TrendingDown size={19} />} tone="blue" trend="down" />
                <Metric title="Waste avoided" value="₱8,450" change="↑ 12% vs. last week" icon={<Leaf size={19} />} tone="purple" trend="up" />
              </div>

              {page === "Overview" && <div className="insight-banner">
                <div className="insight-icon"><Sparkles size={20} /></div>
                <div className="insight-copy"><span>HARVESTGUARD INSIGHT <span className="insight-live">DEMO</span></span><strong>3 items need your attention today</strong><p>Review fresh milk and romaine lettuce first to reduce avoidable waste.</p></div>
                <button className="insight-action" onClick={() => setPage("Recommendations")}>See recommendations <ArrowRight size={16} /></button>
              </div>}

              <div className="chart-grid">
                <section className="panel chart-panel">
                  <div className="panel-heading"><div><h3>Waste cost vs. food saved</h3><p>Daily overview · Last 7 days</p></div><button className="period-button">This week <ChevronDown size={14} /></button></div>
                  <div className="chart-legend"><span><i className="legend-waste" /> Waste cost</span><span><i className="legend-saved" /> Value saved</span></div>
                  <div className="line-chart"><ResponsiveContainer width="100%" height={235}><AreaChart data={trend} margin={{ top: 8, right: 5, left: -16, bottom: 0 }}><defs><linearGradient id="wasteFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#e6a23c" stopOpacity={0.18} /><stop offset="95%" stopColor="#e6a23c" stopOpacity={0} /></linearGradient><linearGradient id="savedFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#25855b" stopOpacity={0.16} /><stop offset="95%" stopColor="#25855b" stopOpacity={0} /></linearGradient></defs><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#edf1ed" /><XAxis dataKey="day" tickLine={false} axisLine={false} tick={{ fill: "#859087", fontSize: 11 }} /><YAxis tickLine={false} axisLine={false} tick={{ fill: "#859087", fontSize: 11 }} tickFormatter={(v: number) => `₱${v / 1000}k`} /><Tooltip formatter={(v) => peso(Number(v))} contentStyle={{ border: "1px solid #e6ece7", borderRadius: 12, fontSize: 12 }} /><Area type="monotone" dataKey="waste" name="Waste cost" stroke="#d89a36" strokeWidth={2.5} fill="url(#wasteFill)" /><Area type="monotone" dataKey="saved" name="Value saved" stroke="#25855b" strokeWidth={2.5} fill="url(#savedFill)" /></AreaChart></ResponsiveContainer></div>
                  <div className="chart-footnote"><span><span className="positive-dot" /> Sample trend</span><span>Values are illustrative, not live business data.</span></div>
                </section>

                <section className="panel priority-panel">
                  <div className="panel-heading"><div><h3>Needs attention</h3><p>Items to review first</p></div><span className="count-pill">3 alerts</span></div>
                  <div className="priority-list">
                    <div className="priority-item"><div className="priority-symbol red"><AlertTriangle size={17} /></div><div className="priority-copy"><strong>Fresh milk</strong><span>Expires today · 18 cartons</span><small>Potential value at risk: ₱1,620</small></div><button aria-label="Review fresh milk alert" onClick={() => acknowledge(1)}><ArrowUpRight size={17} /></button></div>
                    <div className="priority-item"><div className="priority-symbol amber"><Clock3 size={17} /></div><div className="priority-copy"><strong>Romaine lettuce</strong><span>Expires tomorrow · 12 heads</span><small>Potential value at risk: ₱720</small></div><button aria-label="Review lettuce alert" onClick={() => setNotice("Romaine lettuce alert opened. Check actual freshness before deciding what to do.")}><ArrowUpRight size={17} /></button></div>
                    <div className="priority-item"><div className="priority-symbol amber"><Clock3 size={17} /></div><div className="priority-copy"><strong>Chicken breast</strong><span>Expires Oct 31 · 24 kg</span><small>Potential value at risk: ₱4,320</small></div><button aria-label="Review chicken alert" onClick={() => setNotice("Chicken expiry alert opened. Follow applicable food-safety rules and verify storage records.")}><ArrowUpRight size={17} /></button></div>
                  </div>
                  <button className="view-all" onClick={() => setPage("Expiry watch")}>View all expiry alerts <ArrowRight size={15} /></button>
                </section>
              </div>

              <section className="panel inventory-panel">
                <div className="inventory-header"><div className="panel-heading"><div><h3>{inventoryPage ? "Expiry watch list" : "Inventory overview"}</h3><p>{inventoryPage ? "Prioritize items nearing their expiry date." : "A quick look at your tracked perishable stock."}</p></div></div><button className="text-link" onClick={() => setPage(inventoryPage ? "Overview" : "Inventory")}>{inventoryPage ? "Back to overview" : "View all inventory"} <ArrowRight size={15} /></button></div>
                <div className="table-tools"><label className="search-box"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search inventory..." aria-label="Search inventory" /></label><select value={filter} onChange={e => setFilter(e.target.value)} aria-label="Filter inventory"><option>All items</option><option>At risk</option><option>Low stock</option></select><span className="result-count">{visibleItems.length} items</span></div>
                <div className="table-scroll"><table><thead><tr><th>ITEM</th><th>CATEGORY</th><th>QUANTITY</th><th>EXPIRY DATE</th><th>STATUS</th><th className="align-right">STOCK VALUE</th></tr></thead><tbody>
                  {visibleItems.map(item => <tr key={item.id}><td><div className="item-cell"><div className={`product-icon product-${item.category.toLowerCase()}`}>{item.category === "Dairy" ? "◒" : item.category === "Produce" ? "✿" : item.category === "Meat" ? "◇" : "▤"}</div><div><strong>{item.name}</strong><small>HG-{String(item.id).padStart(4, "0")}</small></div></div></td><td><span className="category-text">{item.category}</span></td><td><strong className="quantity">{item.quantity}</strong> <span className="unit">{item.unit}</span></td><td><span className={item.days <= 1 ? "expiry-urgent" : "expiry-text"}>{item.expiry}</span></td><td><Status status={item.status} /></td><td className="align-right value-cell">{peso(item.value)}</td></tr>)}
                  {visibleItems.length === 0 && <tr><td colSpan={6} className="empty-state">No matching items. Try a different search or filter.</td></tr>}
                </tbody></table></div>
                <div className="table-footer"><span>Showing {visibleItems.length} of {items.length} {dataMode === "live" ? "live records" : "demo records"}</span><span><span className="table-dot" /> Sample inventory · Not connected to a live database</span></div>
              </section>
            </>
          )}

          <footer className="footer"><span>© 2026 HarvestGuard AI</span><span><span className="footer-status" /> Demo workspace <span className="footer-separator">·</span> Built to help reduce food waste</span><button onClick={() => setNotice("HarvestGuard AI support and documentation will be linked here as the project develops.")}><CircleHelp size={14} /> Help & support</button></footer>
        </div>
      </main>
    </div>
  );
}

function Metric({ title, value, change, icon, tone, trend: direction }: {
  title: string; value: string; change: string; icon: React.ReactNode; tone: string; trend: "up" | "down";
}) {
  return <section className="metric-card"><div className="metric-top"><span>{title}</span><span className={`metric-icon ${tone}`}>{icon}</span></div><strong className="metric-value">{value}</strong><div className="metric-bottom"><span className={`metric-trend ${direction === "up" ? "trend-up" : "trend-down"}`}>{direction === "up" ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}</span><span>{change}</span></div></section>;
}

function Status({ status }: { status: Item["status"] }) {
  return <span className={`status status-${status.toLowerCase().replace(" ", "-")}`}><i />{status}</span>;
}

function Recommendation({ icon, priority, title, description, impact }: {
  icon: React.ReactNode; priority: string; title: string; description: string; impact: string;
}) {
  return <article className="recommendation-card"><div className="recommendation-icon">{icon}</div><span className="recommendation-priority">{priority}</span><h3>{title}</h3><p>{description}</p><div className="recommendation-impact"><Check size={15} />{impact}</div><button className="recommendation-link" onClick={() => window.alert("Demo suggestion only. No inventory or order was changed.")}>Review action <ArrowRight size={15} /></button></article>;
}

export default App;
