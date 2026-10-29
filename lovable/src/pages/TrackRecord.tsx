import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, TrendingUp } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Button } from "@/components/ui/button";
import { API_BASE } from "@/lib/api";
import TrackRecordMethodology from "@/components/TrackRecordMethodology";

interface Headline {
  record: string;
  win_pct: number | null;
  score_mae: number | null;
  n_picks: number;
  roi_eligible_n: number;
  units: number;
  roi: number;
  streak: number;
}
interface SportRow extends Headline { sport: string; }
interface TrackData {
  methodology: string;
  overall: Headline;
  bySport: SportRow[];
  equityCurve: { date: string; units: number }[];
  recent: { sport: string; date: string; subject: string; side: string; result: string; predHome: number | null; predAway: number | null; }[];
}

const pct = (v: number | null) => (v == null ? "-" : `${(v * 100).toFixed(1)}%`);
const SPORT_LABEL: Record<string, string> = { nba: "NBA", nfl: "NFL", mlb: "MLB", nhl: "NHL", soccer: "Soccer" };

const Stat = ({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) => (
  <div className={`rounded-xl border p-4 ${highlight ? "border-primary/40 bg-primary/5" : "border-border/60 bg-card/40"}`}>
    <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
    <div className={`mt-1 text-3xl font-bold ${highlight ? "text-primary" : ""}`}>{value}</div>
  </div>
);
const Th = ({ children }: { children: ReactNode }) => <th className="text-left font-medium px-4 py-2">{children}</th>;
const Td = ({ children, className = "" }: { children: ReactNode; className?: string }) => <td className={`px-4 py-2 ${className}`}>{children}</td>;
const resultClass = (r: string) => (r === "win" ? "text-emerald-500" : r === "loss" ? "text-red-500" : "text-muted-foreground");

const TrackRecord = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<TrackData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/track-record`);
        const d = await r.json();
        if (d.success) setData(d);
        else setError(d.error || "Failed to load track record");
      } catch {
        setError("Failed to connect to API");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const o = data?.overall;
  const roiEligible = (o?.roi_eligible_n ?? 0) > 0;

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4">
          <Button variant="ghost" size="sm" onClick={() => navigate("/")} className="gap-2 text-muted-foreground hover:text-foreground mb-3">
            <ArrowLeft className="w-4 h-4" /> Back to Today's Games
          </Button>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Track Record</h1>
              <p className="text-sm text-muted-foreground">Every pick is 100% algorithmic &amp; market-blind. Graded, public, honest.</p>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 space-y-8">
        {loading && <div className="text-center py-12 text-muted-foreground">Loading…</div>}
        {error && <div className="bg-destructive/10 border border-destructive/50 text-destructive px-4 py-3 rounded-lg">{error}</div>}

        {o && (
          <>
            <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Stat label="Winner accuracy" value={pct(o.win_pct)} highlight />
              <Stat label="Record (W–L)" value={o.record} />
              <Stat label="Score error (MAE)" value={o.score_mae == null ? "-" : `${o.score_mae} pts`} />
              <Stat label="Graded picks" value={o.n_picks.toLocaleString()} />
            </section>

            <section className="rounded-xl border border-border/60 bg-card/40 p-5">
              {roiEligible ? (
                <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
                  <span className={`text-2xl font-bold ${o.units >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                    {o.units >= 0 ? "+" : ""}{o.units}u
                  </span>
                  <span className="text-muted-foreground">
                    ROI {(o.roi * 100).toFixed(1)}% over {o.roi_eligible_n.toLocaleString()} priced picks
                  </span>
                </div>
              ) : (
                <p className="text-muted-foreground">
                  <span className="font-semibold text-foreground">ROI: accruing.</span> Picks are market-blind, so
                  profit is only counted once each pick is settled at a real closing price. Never fabricated. This
                  fills in as live prices are captured.
                </p>
              )}
            </section>

            {data.equityCurve.length > 0 && (
              <section>
                <h2 className="text-lg font-semibold mb-3">Cumulative units (priced picks)</h2>
                <div className="h-64 rounded-xl border border-border/60 bg-card/40 p-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data.equityCurve}>
                      <XAxis dataKey="date" hide />
                      <YAxis width={40} />
                      <Tooltip />
                      <Line type="monotone" dataKey="units" stroke="hsl(var(--primary))" dot={false} strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </section>
            )}

            <section>
              <h2 className="text-lg font-semibold mb-3">By sport</h2>
              <div className="overflow-x-auto rounded-xl border border-border/60">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40 text-muted-foreground">
                    <tr><Th>Sport</Th><Th>Winner accuracy</Th><Th>Record</Th><Th>Score MAE</Th><Th>Picks</Th></tr>
                  </thead>
                  <tbody>
                    {data.bySport.map((s) => (
                      <tr key={s.sport} className="border-t border-border/50">
                        <Td className="font-medium">{SPORT_LABEL[s.sport] ?? s.sport}</Td>
                        <Td>{pct(s.win_pct)}</Td>
                        <Td>{s.record}</Td>
                        <Td>{s.score_mae == null ? "-" : `${s.score_mae}`}</Td>
                        <Td>{s.n_picks.toLocaleString()}</Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {data.recent.length > 0 && (
              <section>
                <h2 className="text-lg font-semibold mb-3">Recent graded picks</h2>
                <div className="overflow-x-auto rounded-xl border border-border/60">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/40 text-muted-foreground">
                      <tr><Th>Date</Th><Th>Sport</Th><Th>Pick</Th><Th>Predicted</Th><Th>Result</Th></tr>
                    </thead>
                    <tbody>
                      {data.recent.map((r, i) => (
                        <tr key={i} className="border-t border-border/50">
                          <Td>{r.date}</Td>
                          <Td>{SPORT_LABEL[r.sport] ?? r.sport}</Td>
                          <Td className="font-medium">{r.subject} <span className="text-muted-foreground">({r.side})</span></Td>
                          <Td>{r.predHome != null && r.predAway != null ? `${r.predHome}–${r.predAway}` : "-"}</Td>
                          <Td><span className={resultClass(r.result)}>{r.result}</span></Td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            <TrackRecordMethodology text={data.methodology} />
          </>
        )}
      </main>
    </div>
  );
};

export default TrackRecord;
