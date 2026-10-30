import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL } from "./api";

type InventoryOption = {
  id: number;
  name: string;
  quantity: number;
  unit: string;
  value: number;
};

type WasteRecord = {
  id: number;
  item_id: number | null;
  item_name: string;
  quantity: number;
  unit: string;
  unit_cost: number;
  reason: string;
  recorded_at: string;
  total_cost: number;
};

type Analytics = {
  waste_cost_this_week: number;
  currency: string;
  data_source: string;
};

type Props = {
  items: InventoryOption[];
};



function money(value: number) {
  return new Intl.NumberFormat("en-PH", {
    style: "currency",
    currency: "PHP",
    maximumFractionDigits: 2,
  }).format(value);
}

export default function WasteManager({ items }: Props) {
  const [records, setRecords] = useState<WasteRecord[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("Expired");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selected = items.find((item) => item.id === Number(selectedId));
  const quantityNumber = Number(quantity);
  const unitCost =
    selected && selected.quantity > 0
      ? selected.value / selected.quantity
      : 0;

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [wasteResponse, analyticsResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/waste?limit=100`),
        fetch(`${API_BASE_URL}/api/analytics/summary`),
      ]);

      if (!wasteResponse.ok) {
        throw new Error(`Waste API returned HTTP ${wasteResponse.status}`);
      }
      if (!analyticsResponse.ok) {
        throw new Error(
          `Analytics API returned HTTP ${analyticsResponse.status}`
        );
      }

      const [wasteData, analyticsData] = await Promise.all([
        wasteResponse.json(),
        analyticsResponse.json(),
      ]);

      setRecords(wasteData);
      setAnalytics(analyticsData);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load waste records."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function submitWaste(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");

    if (!selected) {
      setError("Select an inventory item first.");
      return;
    }
    if (!Number.isFinite(quantityNumber) || quantityNumber <= 0) {
      setError("Enter a quantity greater than zero.");
      return;
    }
    if (quantityNumber > selected.quantity) {
      setError(
        `Quantity exceeds available stock (${selected.quantity} ${selected.unit}).`
      );
      return;
    }
    if (!reason.trim()) {
      setError("Enter a reason for the waste record.");
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/waste`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          item_id: selected.id,
          item_name: selected.name,
          quantity: quantityNumber,
          unit: selected.unit,
          unit_cost: Number(unitCost.toFixed(4)),
          reason: reason.trim(),
        }),
      });

      if (!response.ok) {
        let message = `Waste API returned HTTP ${response.status}`;
        try {
          const body = await response.json();
          if (body.detail) message = String(body.detail);
        } catch {
          // Keep the HTTP error if the response is not JSON.
        }
        throw new Error(message);
      }

      setQuantity("");
      setNotice("Waste record saved. Inventory stock has been updated.");
      await refresh();

      // Notify the parent dashboard that its inventory data is stale.
      window.location.reload();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to save waste record."
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="waste-manager">
      <div className="section-heading">
        <div>
          <h2>Waste analytics</h2>
          <p>Recorded waste from the connected HarvestGuard database.</p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh records"}
        </button>
      </div>

      <section className="panel" style={{ padding: 20, marginBottom: 20 }}>
        <h3>Recorded waste cost this week</h3>
        <p style={{ fontSize: 28, fontWeight: 700, margin: "10px 0" }}>
          {analytics ? money(analytics.waste_cost_this_week) : "Unavailable"}
        </p>
        <p>
          {analytics
            ? "Calculated from waste records saved in the database."
            : "The analytics API has not returned a result."}
        </p>
        {analytics?.waste_cost_this_week === 0 && (
          <p>No waste cost has been recorded for the current week.</p>
        )}
      </section>

      <section className="panel" style={{ padding: 20, marginBottom: 20 }}>
        <h3>Record food waste</h3>
        <p>
          Saving a record linked to inventory will also reduce its available
          quantity. Confirm the item, amount, and reason before submitting.
        </p>

        <form
          onSubmit={submitWaste}
          style={{
            display: "grid",
            gap: 14,
            gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
            marginTop: 16,
          }}
        >
          <label>
            Inventory item
            <select
              required
              value={selectedId}
              onChange={(event) => setSelectedId(event.target.value)}
              style={{ display: "block", width: "100%", padding: 10, marginTop: 5 }}
            >
              <option value="">Select item</option>
              {items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} — {item.quantity} {item.unit} available
                </option>
              ))}
            </select>
          </label>

          <label>
            Quantity wasted
            <input
              required
              type="number"
              min="0.001"
              step="any"
              max={selected?.quantity}
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              style={{ display: "block", width: "100%", padding: 10, marginTop: 5 }}
            />
          </label>

          <label>
            Reason
            <select
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              style={{ display: "block", width: "100%", padding: 10, marginTop: 5 }}
            >
              <option>Expired</option>
              <option>Spoiled</option>
              <option>Damaged</option>
              <option>Preparation waste</option>
              <option>Other</option>
            </select>
          </label>

          <div>
            <p>
              Estimated record cost:{" "}
              <strong>
                {selected && quantityNumber > 0 && Number.isFinite(quantityNumber)
                  ? money(quantityNumber * unitCost)
                  : money(0)}
              </strong>
            </p>
            <button type="submit" disabled={saving || loading || items.length === 0}>
              {saving ? "Saving..." : "Save waste record"}
            </button>
          </div>
        </form>

        {error && (
          <p role="alert" style={{ color: "#b42318", marginTop: 14 }}>
            {error}
          </p>
        )}
        {notice && (
          <p role="status" style={{ marginTop: 14 }}>
            {notice}
          </p>
        )}
      </section>

      <section className="panel" style={{ padding: 20 }}>
        <h3>Recent waste records</h3>
        <p>Up to 100 records, newest first.</p>

        {loading ? (
          <p>Loading waste records...</p>
        ) : records.length === 0 ? (
          <p>No waste records exist yet. The charts will not invent historical values.</p>
        ) : (
          <div style={{ overflowX: "auto", marginTop: 14 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
              <thead>
                <tr>
                  <th style={{ padding: 10 }}>Date</th>
                  <th style={{ padding: 10 }}>Item</th>
                  <th style={{ padding: 10 }}>Quantity</th>
                  <th style={{ padding: 10 }}>Reason</th>
                  <th style={{ padding: 10 }}>Cost</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr key={record.id}>
                    <td style={{ padding: 10 }}>
                      {new Date(record.recorded_at).toLocaleString()}
                    </td>
                    <td style={{ padding: 10 }}>{record.item_name}</td>
                    <td style={{ padding: 10 }}>
                      {record.quantity} {record.unit}
                    </td>
                    <td style={{ padding: 10 }}>{record.reason}</td>
                    <td style={{ padding: 10 }}>{money(record.total_cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}


