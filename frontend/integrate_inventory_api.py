from pathlib import Path

path = Path(r"C:\Users\kambar\harvestguard-ai\frontend\src\App.tsx")
source = path.read_text(encoding="utf-8")

old_import = 'import { useMemo, useState } from "react";'
new_import = 'import { useEffect, useMemo, useState } from "react";'

old_state = '  const [items, setItems] = useState(initialItems);'
new_state = '''  const [items, setItems] = useState(initialItems);
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
  }, []);'''

replacements = [
    (old_import, new_import, "React import"),
    (old_state, new_state, "inventory API loader"),
]

for old, new, label in replacements:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one match for {label}; found {count}. No source changes written.")
    source = source.replace(old, new, 1)

old_pill = '<div className="demo-pill"><span /> DEMO DATA</div>'
new_pill = '''<div className="demo-pill">
              <span /> {dataMode === "live" ? "LIVE API" : dataMode === "loading" ? "CONNECTING" : "DEMO DATA"}
            </div>'''

if source.count(old_pill) != 1:
    raise SystemExit("Could not safely locate the data-mode badge. No source changes written.")
source = source.replace(old_pill, new_pill, 1)

old_footer = 'Showing {visibleItems.length} of {items.length} demo records'
new_footer = 'Showing {visibleItems.length} of {items.length} {dataMode === "live" ? "live records" : "demo records"}'

if source.count(old_footer) != 1:
    raise SystemExit("Could not safely locate the inventory footer. No source changes written.")
source = source.replace(old_footer, new_footer, 1)

# Write only after every expected replacement has passed validation.
path.write_text(source, encoding="utf-8")
print("PASS: Inventory API integration added.")
