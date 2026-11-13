"use client";

import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Bike,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Download,
  Flag,
  Gauge,
  LayoutDashboard,
  ListFilter,
  LockKeyhole,
  Mountain,
  Route,
  ShieldCheck,
  Sparkles,
  Timer,
  Trophy,
  Upload,
  X,
} from "lucide-react";

type Effort = { order: number; duration_seconds: number };
type Segment = {
  label: string;
  efforts: Effort[];
  counts: { rides: number; accepted: number; rejected: number };
};
type Snapshot = {
  schema_version: number;
  data_kind: "synthetic" | "real";
  segments: Segment[];
};
type View = "overview" | "efforts" | "methodology";

function time(seconds: number) {
  const rounded = Math.round(seconds);
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, "0")}`;
}

function Trend({
  efforts,
  selected,
  onSelect,
  best,
}: {
  efforts: Effort[];
  selected: number | null;
  onSelect: (order: number) => void;
  best: number;
}) {
  if (!efforts.length)
    return (
      <div className="empty-state">
        <Route size={32} />
        <h3>No matched efforts yet</h3>
        <p>
          Import rides through your selected climb, then generate an approved
          snapshot.
        </p>
      </div>
    );
  const low =
    Math.floor(
      (Math.min(best, ...efforts.map((e) => e.duration_seconds)) - 25) / 30,
    ) * 30;
  const high =
    Math.ceil((Math.max(...efforts.map((e) => e.duration_seconds)) + 25) / 30) *
    30;
  const x = (i: number) => 66 + i * (712 / Math.max(1, efforts.length - 1));
  const y = (n: number) => 30 + ((high - n) / (high - low)) * 208;
  const line = efforts
    .map((e, i) => `${i ? "L" : "M"}${x(i)},${y(e.duration_seconds)}`)
    .join(" ");
  const chosen =
    efforts.find((e) => e.order === selected) ?? efforts[efforts.length - 1];
  return (
    <>
      <div className="chart-wrap">
        <svg
          viewBox="0 0 820 290"
          role="group"
          aria-label="Elapsed climb times in chronological effort order. Lower times are faster."
        >
          <defs>
            <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4169df" stopOpacity=".13" />
              <stop offset="100%" stopColor="#4169df" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[0, 1, 2, 3, 4].map((i) => {
            const n = low + ((high - low) * i) / 4;
            return (
              <g key={i}>
                <line
                  x1="66"
                  x2="790"
                  y1={y(n)}
                  y2={y(n)}
                  stroke="#e9edf3"
                  strokeDasharray="3 5"
                />
                <text
                  x="44"
                  y={y(n) + 4}
                  textAnchor="end"
                  className="axis-label"
                >
                  {time(n)}
                </text>
              </g>
            );
          })}
          <path
            d={`${line} L${x(efforts.length - 1)},248 L66,248 Z`}
            fill="url(#area)"
          />
          <line
            x1="66"
            x2="790"
            y1={y(best)}
            y2={y(best)}
            stroke="#339b7d"
            strokeDasharray="5 5"
            opacity=".5"
          />
          <path
            d={line}
            fill="none"
            stroke="#4669da"
            strokeWidth="3"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          {efforts.map((e, i) => (
            <g key={e.order}>
              {e.order === chosen.order && (
                <line
                  x1={x(i)}
                  x2={x(i)}
                  y1="22"
                  y2="248"
                  stroke="#b8c7ef"
                  strokeDasharray="4 4"
                />
              )}
              <circle
                cx={x(i)}
                cy={y(e.duration_seconds)}
                r={e.order === chosen.order ? 8 : 5}
                fill={e.duration_seconds === best ? "#218465" : "#4669da"}
                stroke="white"
                strokeWidth="3"
              />
              <text x={x(i)} y="278" textAnchor="middle" className="axis-label">
                {String(e.order).padStart(2, "0")}
              </text>
              <g
                role="button"
                tabIndex={0}
                aria-label={`Select effort ${e.order}, ${time(e.duration_seconds)}`}
                onClick={() => onSelect(e.order)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(e.order);
                  }
                }}
                className="chart-target"
              >
                <circle
                  cx={x(i)}
                  cy={y(e.duration_seconds)}
                  r="17"
                  fill="transparent"
                >
                  <title>{`Effort ${e.order}: ${time(e.duration_seconds)}`}</title>
                </circle>
              </g>
            </g>
          ))}
        </svg>
      </div>
      <div className="chart-footer">
        <span>
          <i className="legend-dot blue" />
          Elapsed time <span className="muted"> · lower is faster</span>
        </span>
        <span>
          <i className="legend-dash" />
          Personal best
        </span>
        <strong>
          Effort {String(chosen.order).padStart(2, "0")}{" "}
          <b>{time(chosen.duration_seconds)}</b>
        </strong>
      </div>
    </>
  );
}

function RouteSchematic() {
  return (
    <svg
      className="route-schematic"
      viewBox="0 0 310 174"
      role="img"
      aria-label="Illustration of a directed climb: start, checkpoint, finish. Not a geographic map."
    >
      <defs>
        <pattern id="dots" width="16" height="16" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="1" fill="#d7dfdf" />
        </pattern>
      </defs>
      <rect width="310" height="174" fill="#f2f6f5" />
      <rect width="310" height="174" fill="url(#dots)" />
      <g fill="none" stroke="#dbe4df" strokeWidth="1.2">
        <path d="M-30 150Q40 8 140 50T340 5" />
        <path d="M-30 172Q40 30 140 72T340 27" />
        <path d="M-30 194Q40 52 140 94T340 49" />
        <path d="M-30 216Q40 74 140 116T340 71" />
        <path d="M-30 238Q40 96 140 138T340 93" />
      </g>
      <path
        d="M43 137C80 137 64 92 108 100S157 119 164 76S213 88 258 35"
        stroke="white"
        strokeWidth="12"
        fill="none"
      />
      <path
        d="M43 137C80 137 64 92 108 100S157 119 164 76S213 88 258 35"
        stroke="#4b70d6"
        strokeWidth="4"
        fill="none"
        strokeLinecap="round"
      />
      <g stroke="#4b70d6" strokeWidth="2">
        <circle cx="43" cy="137" r="7" fill="white" />
        <circle cx="164" cy="76" r="7" fill="white" />
        <circle cx="258" cy="35" r="7" fill="#4b70d6" />
      </g>
      <g fontSize="11" fill="#425651" fontFamily="inherit">
        <text x="25" y="162">
          Start
        </text>
        <text x="118" y="51">
          Checkpoint
        </text>
        <text x="240" y="18">
          Finish
        </text>
      </g>
    </svg>
  );
}

function ImportDialog({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [source, setSource] = useState<"strava" | "gpx">("strava");
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  const command =
    source === "strava"
      ? "ride-replay strava-sync --connect --activity-id YOUR_ACTIVITY_ID\nride-replay import data/strava"
      : 'ride-replay import "C:\\path\\to\\your\\rides"';
  return (
    <dialog
      ref={dialog}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      aria-labelledby="import-title"
    >
      <div className="dialog-head">
        <span className="icon-tile">
          <Upload size={21} />
        </span>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close import instructions"
        >
          <X size={20} />
        </button>
      </div>
      <h2 id="import-title">Bring your own rides.</h2>
      <p>
        Keep your tracks private. Import on your computer, compare a climb, and
        share only the efforts you approve.
      </p>
      <div className="segmented source-tabs">
        <button
          className={source === "strava" ? "active" : ""}
          onClick={() => {
            setSource("strava");
            setCopied(false);
          }}
        >
          From Strava
        </button>
        <button
          className={source === "gpx" ? "active" : ""}
          onClick={() => {
            setSource("gpx");
            setCopied(false);
          }}
        >
          GPX files
        </button>
      </div>
      {source === "strava" ? (
        <>
          <h3>Connect through the local importer</h3>
          <p>
            Create your Strava API app, then run these commands from your
            project. Enter its client ID and secret locally, and approve read
            access in your browser. Replace the activity ID with your own ride.
            Add <code>--include-private</code> for Only You activities.
          </p>
        </>
      ) : (
        <>
          <h3>Choose your ride folder</h3>
          <p>
            Export two or more rides with GPS timestamps. Replace the example
            path below with the folder containing your GPX files.
          </p>
        </>
      )}
      <pre>{command}</pre>
      <button
        className="secondary full"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(command);
            setCopied(true);
          } catch {
            setCopied(false);
          }
        }}
      >
        {copied ? <Check size={16} /> : <Download size={16} />}
        {copied ? "Copied commands" : "Copy commands"}
      </button>
      <div className="privacy-note">
        <LockKeyhole size={17} />
        <span>
          This demo does not receive ride uploads or access your Strava account.
          Tokens stay on your computer.
        </span>
      </div>
      <a
        className="text-link"
        href="https://github.com/calin-andrei-rotaru/ride-replay#use-your-own-rides"
        target="_blank"
        rel="noreferrer"
      >
        Read the full import guide <ArrowUpRight size={15} />
      </a>
    </dialog>
  );
}

export default function Dashboard() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [view, setView] = useState<View>("overview");
  const [segmentIndex, setSegmentIndex] = useState(0);
  const [range, setRange] = useState("all");
  const [sort, setSort] = useState("recent");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [showImport, setShowImport] = useState(false);

  useEffect(() => {
    fetch("/snapshot.json")
      .then((response) => {
        if (!response.ok) throw new Error("Snapshot unavailable");
        return response.json();
      })
      .then((data: Snapshot) => {
        if (
          data.schema_version !== 1 ||
          !Array.isArray(data.segments) ||
          !["real", "synthetic"].includes(data.data_kind)
        )
          throw new Error("Unsupported snapshot");
        setSnapshot(data);
      })
      .catch(() =>
        setError(
          "The effort snapshot could not be loaded. Reload the page to try again.",
        ),
      );
  }, []);

  const segment = snapshot?.segments[segmentIndex];
  const all = segment?.efforts ?? [];
  const filtered = range === "recent" ? all.slice(-6) : all;
  const best = all.length ? Math.min(...all.map((e) => e.duration_seconds)) : 0;
  const latest = all[all.length - 1];
  const improvement =
    all.length > 1
      ? all[0].duration_seconds - (latest?.duration_seconds ?? 0)
      : 0;
  const percent =
    all.length > 1 ? (improvement / all[0].duration_seconds) * 100 : 0;
  const sorted = [...filtered].sort((a, b) =>
    sort === "fastest"
      ? a.duration_seconds - b.duration_seconds
      : b.order - a.order,
  );
  const visible = sorted.slice(page * 6, page * 6 + 6);
  const isDemo = snapshot?.data_kind === "synthetic";

  function changeView(next: View) {
    setView(next);
    setPage(0);
  }
  function download() {
    const csv = [
      "effort_order,duration_seconds,difference_from_best_seconds",
      ...filtered.map(
        (e) => `${e.order},${e.duration_seconds},${e.duration_seconds - best}`,
      ),
    ].join("\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "ride-replay-efforts.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="Ride Replay home">
          <span className="brand-mark">
            <Route size={23} strokeWidth={2.3} />
          </span>
          ride<span className="brand-light">replay</span>
          <span className="brand-period">.</span>
        </a>
        <div className="workspace-label">Your training, in perspective</div>
        <nav aria-label="Main navigation">
          {(
            [
              ["overview", LayoutDashboard, "Overview"],
              ["efforts", Activity, "Effort history"],
              ["methodology", Route, "How it works"],
            ] as const
          ).map(([key, Icon, label]) => (
            <button
              key={key}
              className={`nav-item ${view === key ? "active" : ""}`}
              onClick={() => changeView(key)}
              aria-current={view === key ? "page" : undefined}
            >
              <Icon size={19} />
              {label}
              {key === "overview" && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="private-card">
            <ShieldCheck size={23} />
            <h3>Your routes stay yours.</h3>
            <p>Only approved, anonymous effort times leave your computer.</p>
            <button
              className="text-link"
              onClick={() => changeView("methodology")}
            >
              Our approach <ArrowRight size={14} />
            </button>
          </div>
          <div className="workspace">
            <span className="avatar">
              <Bike size={20} />
            </span>
            <span>
              <strong>{isDemo ? "Demo workspace" : "Ride workspace"}</strong>
              <small>
                {isDemo
                  ? "Explore with sample rides"
                  : "Approved effort snapshot"}
              </small>
            </span>
            <LockKeyhole size={14} />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={14} />
            <strong>
              {view === "overview"
                ? "Overview"
                : view === "efforts"
                  ? "Effort history"
                  : "How it works"}
            </strong>
          </div>
          <div className="topbar-right">
            <span className="snapshot-status">
              <span />
              {isDemo
                ? "Synthetic demo"
                : snapshot
                  ? "Snapshot ready"
                  : "Loading snapshot"}
            </span>
            <button
              className="icon-button"
              onClick={() => changeView("methodology")}
              aria-label="How Ride Replay works"
            >
              <CircleHelp size={19} />
            </button>
            <span className="profile">RR</span>
          </div>
        </header>
        <main id="main-content">
          <div className="page-heading">
            <div>
              <div className="heading-note">
                <Bike size={16} />
                Same climb. A new perspective.
              </div>
              <h1>
                {view === "overview"
                  ? "Every climb tells a story."
                  : view === "efforts"
                    ? "Your efforts, side by side."
                    : "A fair comparison starts here."}
              </h1>
              <p>
                {view === "methodology"
                  ? "Simple rules, transparent results, and a little respect for your data."
                  : "See your progress on the roads you keep coming back to."}
              </p>
            </div>
            <button className="primary" onClick={() => setShowImport(true)}>
              <Upload size={16} />
              Import rides
            </button>
          </div>
          {error ? (
            <div role="alert" className="notice error">
              {error}
              <button onClick={() => location.reload()}>Reload</button>
            </div>
          ) : !snapshot ? (
            <div role="status" className="loading">
              Loading your effort snapshot…
            </div>
          ) : (
            <>
              {isDemo && (
                <div className="demo-banner">
                  <span className="demo-icon">
                    <Sparkles size={17} />
                  </span>
                  <p>
                    <strong>A little preview of your progress.</strong> You’re
                    exploring synthetic rides. Connect your own when you’re
                    ready.
                  </p>
                  <button onClick={() => setShowImport(true)}>
                    Use my rides <ArrowRight size={15} />
                  </button>
                </div>
              )}
              {view === "methodology" ? (
                <section className="methodology-page">
                  <div className="section-title">
                    <span className="icon-tile">
                      <Route size={21} />
                    </span>
                    <div>
                      <h2>One climb. Three checkpoints.</h2>
                      <p>
                        Efforts need to follow the same direction, on one
                        continuous track.
                      </p>
                    </div>
                  </div>
                  <div className="methodology-layout">
                    <RouteSchematic />
                    <div>
                      <h3>What counts as the same climb?</h3>
                      <p>
                        The matcher looks for the start, an intermediate
                        checkpoint, and the finish in that order. Passing near
                        both endpoints while taking another route doesn’t count.
                      </p>
                      <p>
                        The initial local defaults use a 35 m radius, at least 5
                        samples, a maximum 30 second sampling gap, and a 25 m/s
                        GPS jump threshold. Tune these against your first real
                        rides before publishing results.
                      </p>
                    </div>
                  </div>
                  <div className="method-grid">
                    <article>
                      <Timer />
                      <h3>Elapsed time, honestly measured</h3>
                      <p>
                        Timing uses the first recorded sample inside each
                        geofence. Pauses count. Crossing estimates are not
                        interpolated, so sampling can make a difference of up to
                        one sampling interval at each endpoint.
                      </p>
                    </article>
                    <article>
                      <ShieldCheck />
                      <h3>A small, approved snapshot</h3>
                      <p>
                        Public data contains a segment label, anonymous effort
                        order, rounded seconds, and aggregate counts. It
                        excludes GPS coordinates, ride dates, filenames, and
                        private ride identifiers.
                      </p>
                    </article>
                    <article>
                      <ListFilter />
                      <h3>Quality before quantity</h3>
                      <p>
                        Reverse passes, missing checkpoints, incomplete tracks,
                        missing times, long gaps, and GPS jumps are rejected.
                        Detailed rejection reasons stay in your private local
                        results.
                      </p>
                    </article>
                    <article>
                      <Bike />
                      <h3>Synthetic until you connect</h3>
                      <p>
                        The included fixture proves the local workflow. It does
                        not establish your fitness progress, verify a real
                        climb, or claim a Databricks run.
                      </p>
                    </article>
                  </div>
                </section>
              ) : (
                <>
                  <div className="filter-row">
                    <div className="segment-picker">
                      <span className="icon-tile small">
                        <Mountain size={19} />
                      </span>
                      <div>
                        <label htmlFor="segment">Selected climb</label>
                        <select
                          id="segment"
                          value={segmentIndex}
                          onChange={(event) => {
                            setSegmentIndex(Number(event.target.value));
                            setSelected(null);
                            setPage(0);
                          }}
                        >
                          {snapshot.segments.map((s, i) => (
                            <option key={i} value={i}>
                              {s.label.replace(" · synthetic", "")}
                            </option>
                          ))}
                        </select>
                      </div>
                      <ChevronDown size={16} />
                    </div>
                    <div className="range-picker">
                      <label htmlFor="range">
                        <ListFilter size={15} />
                        Show
                      </label>
                      <select
                        id="range"
                        value={range}
                        onChange={(event) => {
                          setRange(event.target.value);
                          setPage(0);
                          setSelected(null);
                        }}
                      >
                        <option value="all">All efforts</option>
                        <option value="recent">Latest 6 efforts</option>
                      </select>
                    </div>
                  </div>
                  {view === "overview" && (
                    <div className="stats-grid">
                      <article className="stat-card">
                        <div className="stat-top">
                          <span>Personal best</span>
                          <Trophy size={18} />
                        </div>
                        <div className="stat-number">
                          {best ? time(best) : "—"}
                          <span>min</span>
                        </div>
                        <div className="stat-context green">
                          <Trophy size={13} />
                          {all.length
                            ? `Fastest of ${all.length} accepted efforts`
                            : "Your first effort starts here"}
                        </div>
                      </article>
                      <article className="stat-card">
                        <div className="stat-top">
                          <span>Latest effort</span>
                          <Timer size={18} />
                        </div>
                        <div className="stat-number">
                          {latest ? time(latest.duration_seconds) : "—"}
                          <span>min</span>
                        </div>
                        <div className="stat-context">
                          {latest && latest.duration_seconds === best ? (
                            <>
                              <span className="mini-tag">New best</span> A good
                              day on the climb
                            </>
                          ) : latest ? (
                            `${latest.duration_seconds - best}s from your best`
                          ) : (
                            "No accepted efforts yet"
                          )}
                        </div>
                      </article>
                      <article className="stat-card">
                        <div className="stat-top">
                          <span>Since your first effort</span>
                          <Gauge size={18} />
                        </div>
                        <div className="stat-number">
                          {all.length > 1
                            ? `${Math.abs(percent).toFixed(1)}%`
                            : "—"}
                          <span>
                            {all.length > 1
                              ? improvement >= 0
                                ? "faster"
                                : "slower"
                              : ""}
                          </span>
                        </div>
                        <div
                          className={`stat-context ${improvement >= 0 ? "green" : ""}`}
                        >
                          <ArrowDownRight size={15} />
                          {all.length > 1
                            ? `${time(Math.abs(improvement))} ${improvement >= 0 ? "quicker" : "longer"} from first to latest`
                            : "Compare at least two efforts"}
                        </div>
                      </article>
                    </div>
                  )}
                  <div
                    className={
                      view === "overview"
                        ? "content-grid"
                        : "content-grid full-width"
                    }
                  >
                    <div className="left-column">
                      <section className="panel chart-panel">
                        <div className="panel-heading">
                          <div>
                            <h2>The bigger picture</h2>
                            <p>Your climb times, one effort at a time.</p>
                          </div>
                          <span className="subtle-badge">
                            <Activity size={13} />
                            {filtered.length} efforts
                          </span>
                        </div>
                        <Trend
                          efforts={filtered}
                          selected={selected}
                          onSelect={setSelected}
                          best={best}
                        />
                        <div className="chart-caption">
                          <span>Chronological effort order</span>
                          <span>Times rounded to the nearest second</span>
                        </div>
                      </section>
                      <section className="panel efforts-panel">
                        <div className="panel-heading">
                          <div>
                            <h2>
                              {view === "overview"
                                ? "A closer look"
                                : "Effort history"}
                            </h2>
                            <p>Every accepted passage on this climb.</p>
                          </div>
                          <button
                            className="secondary compact"
                            onClick={download}
                            disabled={!filtered.length}
                          >
                            <Download size={14} />
                            Export CSV
                          </button>
                        </div>
                        <div className="table-tools">
                          <span>{filtered.length} accepted efforts</span>
                          <label>
                            Sort by{" "}
                            <select
                              aria-label="Sort efforts"
                              value={sort}
                              onChange={(event) => {
                                setSort(event.target.value);
                                setPage(0);
                              }}
                            >
                              <option value="recent">Most recent</option>
                              <option value="fastest">Fastest first</option>
                            </select>
                          </label>
                        </div>
                        <div className="table-scroll">
                          <table>
                            <thead>
                              <tr>
                                <th>Effort</th>
                                <th>Elapsed time</th>
                                <th>From best</th>
                                <th>Result</th>
                              </tr>
                            </thead>
                            <tbody>
                              {visible.map((e) => (
                                <tr
                                  key={e.order}
                                  className={
                                    selected === e.order ? "selected-row" : ""
                                  }
                                >
                                  <td>
                                    <button
                                      className="effort-link"
                                      onClick={() => setSelected(e.order)}
                                    >
                                      <span className="effort-icon">
                                        <Bike size={15} />
                                      </span>
                                      Effort {String(e.order).padStart(2, "0")}
                                    </button>
                                  </td>
                                  <td className="duration">
                                    {time(e.duration_seconds)}
                                  </td>
                                  <td
                                    className={
                                      e.duration_seconds === best
                                        ? "green"
                                        : "muted"
                                    }
                                  >
                                    {e.duration_seconds === best
                                      ? "—"
                                      : `+${time(e.duration_seconds - best)}`}
                                  </td>
                                  <td>
                                    {e.duration_seconds === best ? (
                                      <span className="result-best">
                                        <Trophy size={12} />
                                        Personal best
                                      </span>
                                    ) : (
                                      <span className="result-valid">
                                        <Check size={13} />
                                        Matched
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        {!filtered.length && (
                          <p className="table-empty">
                            No accepted efforts in this snapshot.
                          </p>
                        )}
                        <div className="table-pagination">
                          <span>
                            {filtered.length
                              ? `${page * 6 + 1}–${Math.min((page + 1) * 6, filtered.length)} of ${filtered.length} efforts`
                              : "0 efforts"}
                          </span>
                          <div>
                            <button
                              className="icon-button"
                              disabled={page === 0}
                              onClick={() => setPage(page - 1)}
                              aria-label="Previous efforts page"
                            >
                              <ChevronLeft size={16} />
                            </button>
                            <button
                              className="icon-button"
                              disabled={(page + 1) * 6 >= filtered.length}
                              onClick={() => setPage(page + 1)}
                              aria-label="Next efforts page"
                            >
                              <ChevronRight size={16} />
                            </button>
                          </div>
                        </div>
                      </section>
                    </div>
                    {view === "overview" && (
                      <aside className="right-column">
                        <section className="panel climb-panel">
                          <div className="panel-heading">
                            <div>
                              <h2>Know your climb</h2>
                              <p>A familiar road. A fresh challenge.</p>
                            </div>
                            <Mountain size={19} className="muted" />
                          </div>
                          <RouteSchematic />
                          <div className="climb-details">
                            <h3>
                              {segment?.label.replace(" · synthetic", "") ??
                                "Choose a climb"}
                            </h3>
                            <span className="direction-label">
                              <ArrowUpRight size={14} />
                              One directed segment
                            </span>
                            <div className="checkpoint-row">
                              <span>
                                <i />
                                Start
                              </span>
                              <span className="connecting-line" />
                              <span>
                                <i />
                                Checkpoint
                              </span>
                              <span className="connecting-line" />
                              <span>
                                <Flag size={12} />
                                Finish
                              </span>
                            </div>
                            <p className="schematic-note">
                              Route illustration, not a GPS map.
                            </p>
                          </div>
                        </section>
                        <section className="panel quality-panel">
                          <div className="quality-heading">
                            <span className="icon-tile mint">
                              <CheckCheck size={19} />
                            </span>
                            <h2>Good data. Fair comparisons.</h2>
                          </div>
                          <p>
                            Only complete, correctly directed passages make it
                            into your progress.
                          </p>
                          <div className="quality-count">
                            <span>
                              <i className="legend-dot green-dot" />
                              Accepted efforts
                            </span>
                            <strong>{segment?.counts.accepted ?? 0}</strong>
                          </div>
                          <div className="quality-count">
                            <span>
                              <i className="legend-dot grey-dot" />
                              Excluded candidates
                            </span>
                            <strong>{segment?.counts.rejected ?? 0}</strong>
                          </div>
                          <div className="quality-divider" />
                          <button
                            className="text-link"
                            onClick={() => changeView("methodology")}
                          >
                            See the matching rules <ArrowRight size={14} />
                          </button>
                        </section>
                        <div className="little-note">
                          <span>↗</span>
                          <p>
                            Progress isn’t always a straight line.
                            <br />
                            <strong>Keep showing up.</strong>
                          </p>
                        </div>
                      </aside>
                    )}
                  </div>
                </>
              )}
              <footer className="page-footer">
                <span>
                  <Route size={14} />
                  Made for the roads you ride again.
                </span>
                <span>
                  <LockKeyhole size={12} />
                  {isDemo
                    ? "Synthetic data · no personal tracks"
                    : "Approved snapshot · no personal tracks"}
                </span>
              </footer>
            </>
          )}
        </main>
      </div>
      {showImport && <ImportDialog onClose={() => setShowImport(false)} />}
    </div>
  );
}
