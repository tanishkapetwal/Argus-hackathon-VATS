// Conversational intake: a guided, chat-style wizard that collects a UserProfile through a short
// back-and-forth using dropdowns, number/text boxes, and chip inputs (no free-text NLP needed).
// When complete it hands the profile to the parent, which kicks off the multi-agent debate.

import { useEffect, useRef, useState } from "react";
import { DEMO_PROFILES } from "../lib/demoProfiles";
import type { ActivityLevel, Goal, Sex, UserProfile } from "../lib/types";

type Msg = { role: "bot" | "user"; text: string };

const GOALS: { value: Goal; label: string }[] = [
  { value: "fat_loss", label: "Lose fat" },
  { value: "muscle_gain", label: "Build muscle" },
  { value: "maintenance", label: "Maintain weight" },
  { value: "general_health", label: "General health" },
  { value: "endurance", label: "Endurance" },
];
const SEXES: Sex[] = ["male", "female", "other"];
const ACTIVITY: { value: ActivityLevel; label: string }[] = [
  { value: "sedentary", label: "Sedentary — desk job, little movement" },
  { value: "light", label: "Lightly active — some walking" },
  { value: "moderate", label: "Moderately active — regular exercise" },
  { value: "active", label: "Active — daily training" },
  { value: "very_active", label: "Very active — physical job + training" },
];
const DIETS = ["no preference", "vegetarian", "vegan", "high protein, vegetarian",
  "non-vegetarian", "pescatarian", "keto"];
const EQUIPMENT = ["dumbbells", "gym membership", "resistance bands", "yoga mat", "bodyweight only"];

const BASE: UserProfile = {
  age: 30, sex: "male", height_cm: 175, weight_kg: 75, activity_level: "moderate",
  goal: "general_health", target_weight_kg: null, timeframe_weeks: null,
  medical_conditions: [], medications: [], allergies: [],
  budget_weekly: 2000, currency: "INR", diet_preference: "no preference",
  disliked_foods: [], equipment_access: [], days_per_week: 4, session_minutes: 45, notes: null,
};

const QUESTIONS = [
  "Hi! I'm your planning assistant. I'll brief a team of specialist agents (medical, nutrition, fitness, budget…) to build you one coherent plan. First — what's your main goal?",
  "Great. Tell me a little about you.",
  "How active are you on a typical day? (a goal weight + timeframe are optional)",
  "Safety comes first — any medical conditions, injuries, or allergies the agents must respect?",
  "How do you like to eat?",
  "What's your weekly budget for food + fitness?",
  "Last bit — your training setup.",
  "Here's your profile. Ready to let the agents debate it?",
];

const btn = "rounded-lg px-3 py-1.5 text-sm transition";
const ghost = `${btn} border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10`;
const primary =
  `${btn} bg-gradient-to-r from-indigo-500 to-cyan-500 font-medium text-white shadow-glow hover:brightness-110`;
const inputCls =
  "rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-sm text-slate-100 placeholder:text-slate-500 focus:border-cyan-400/60 focus:outline-none";

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</span>
      {children}
    </label>
  );
}

function Chips({ values, onChange, placeholder, suggestions }: {
  values: string[]; onChange: (v: string[]) => void; placeholder: string; suggestions?: string[];
}) {
  const [text, setText] = useState("");
  const add = (v: string) => {
    const t = v.trim();
    if (t && !values.includes(t)) onChange([...values, t]);
    setText("");
  };
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap gap-1.5">
        {values.map((v) => (
          <span key={v} className="flex items-center gap-1 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2 py-0.5 text-xs text-cyan-200">
            {v}
            <button onClick={() => onChange(values.filter((x) => x !== v))} className="text-cyan-300/70 hover:text-white">×</button>
          </span>
        ))}
      </div>
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(text); } }}
        placeholder={placeholder}
        className={inputCls}
      />
      {suggestions && (
        <div className="flex flex-wrap gap-1">
          {suggestions.filter((s) => !values.includes(s)).map((s) => (
            <button key={s} onClick={() => add(s)} className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-slate-400 hover:border-cyan-400/40 hover:text-cyan-200">
              + {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function ChatIntake({ onComplete }: { onComplete: (p: UserProfile) => void }) {
  const [draft, setDraft] = useState<UserProfile>(BASE);
  const [step, setStep] = useState(0);
  const [messages, setMessages] = useState<Msg[]>([{ role: "bot", text: QUESTIONS[0] }]);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, step]);

  const advance = (patch: Partial<UserProfile>, echo: string) => {
    setDraft((d) => ({ ...d, ...patch }));
    setStep((s) => {
      const next = s + 1;
      setMessages((m) => [...m, { role: "user", text: echo },
        ...(QUESTIONS[next] ? [{ role: "bot" as const, text: QUESTIONS[next] }] : [])]);
      return next;
    });
  };
  const back = () => {
    setStep((s) => Math.max(0, s - 1));
    setMessages((m) => m.slice(0, Math.max(1, m.length - 2)));
  };

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col">
      <div className="flex-1 space-y-3 overflow-auto px-1 py-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex animate-fade-up ${m.role === "user" ? "justify-end" : "gap-2.5"}`}>
            {m.role === "bot" && (
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-cyan-500 text-sm shadow-glow">✦</div>
            )}
            <div className={m.role === "user"
              ? "max-w-[80%] rounded-2xl rounded-tr-sm bg-gradient-to-r from-indigo-500/90 to-violet-500/90 px-3.5 py-2 text-sm text-white"
              : "max-w-[85%] rounded-2xl rounded-tl-sm border border-white/10 bg-white/[0.05] px-3.5 py-2 text-sm text-slate-200"}>
              {m.text}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div className="glass mt-2 p-4 animate-fade-up">
        {step === 0 && <GoalStep onSubmit={advance} onComplete={onComplete} />}
        {step === 1 && <AboutStep draft={draft} onSubmit={advance} onBack={back} />}
        {step === 2 && <ActivityStep draft={draft} onSubmit={advance} onBack={back} />}
        {step === 3 && <HealthStep draft={draft} onSubmit={advance} onBack={back} />}
        {step === 4 && <FoodStep draft={draft} onSubmit={advance} onBack={back} />}
        {step === 5 && <BudgetStep draft={draft} onSubmit={advance} onBack={back} />}
        {step === 6 && <TrainingStep draft={draft} onSubmit={advance} onBack={back} />}
        {step === 7 && <ReviewStep draft={draft} onComplete={onComplete} onBack={back} />}
      </div>
    </div>
  );
}

type Sub = (patch: Partial<UserProfile>, echo: string) => void;

function Row({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{children}</div>;
}
function Actions({ onBack, label = "Continue", disabled }: { onBack?: () => void; label?: string; disabled?: boolean }) {
  return (
    <div className="mt-3 flex items-center justify-between">
      {onBack ? <button type="button" onClick={onBack} className={ghost}>Back</button> : <span />}
      <button type="submit" disabled={disabled} className={`${primary} disabled:opacity-40`}>{label}</button>
    </div>
  );
}

function GoalStep({ onSubmit, onComplete }: { onSubmit: Sub; onComplete: (p: UserProfile) => void }) {
  const [goal, setGoal] = useState<Goal>("fat_loss");
  return (
    <div>
      <form onSubmit={(e) => { e.preventDefault();
        onSubmit({ goal }, `My goal is to ${GOALS.find((g) => g.value === goal)!.label.toLowerCase()}.`); }}>
        <div className="flex flex-wrap gap-2">
          {GOALS.map((g) => (
            <button type="button" key={g.value} onClick={() => setGoal(g.value)}
              className={`${btn} border ${goal === g.value ? "border-cyan-400/60 bg-cyan-400/10 text-cyan-200 shadow-glow-cyan" : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"}`}>
              {g.label}
            </button>
          ))}
        </div>
        <Actions />
      </form>
      <div className="mt-3 border-t border-white/10 pt-3">
        <p className="mb-1.5 text-[11px] text-slate-500">In a hurry? Load a ready-made scenario:</p>
        <div className="flex flex-wrap gap-2">
          {DEMO_PROFILES.map((d) => (
            <button key={d.id} title={d.description} onClick={() => onComplete(d.profile)}
              className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 hover:border-indigo-400/40 hover:text-indigo-200">
              ⚡ {d.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function AboutStep({ draft, onSubmit, onBack }: { draft: UserProfile; onSubmit: Sub; onBack: () => void }) {
  const [sex, setSex] = useState<Sex>(draft.sex);
  const [age, setAge] = useState(draft.age);
  const [h, setH] = useState(draft.height_cm);
  const [w, setW] = useState(draft.weight_kg);
  return (
    <form onSubmit={(e) => { e.preventDefault();
      onSubmit({ sex, age, height_cm: h, weight_kg: w }, `${sex}, ${age}y, ${h} cm, ${w} kg.`); }}>
      <Row>
        <Labeled label="Sex">
          <select className={inputCls} value={sex} onChange={(e) => setSex(e.target.value as Sex)}>
            {SEXES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Labeled>
        <Labeled label="Age"><input type="number" className={inputCls} value={age} onChange={(e) => setAge(+e.target.value)} /></Labeled>
        <Labeled label="Height (cm)"><input type="number" className={inputCls} value={h} onChange={(e) => setH(+e.target.value)} /></Labeled>
        <Labeled label="Weight (kg)"><input type="number" className={inputCls} value={w} onChange={(e) => setW(+e.target.value)} /></Labeled>
      </Row>
      <Actions onBack={onBack} disabled={!age || !h || !w} />
    </form>
  );
}

function ActivityStep({ draft, onSubmit, onBack }: { draft: UserProfile; onSubmit: Sub; onBack: () => void }) {
  const [act, setAct] = useState<ActivityLevel>(draft.activity_level);
  const [tw, setTw] = useState<string>(draft.target_weight_kg?.toString() ?? "");
  const [tf, setTf] = useState<string>(draft.timeframe_weeks?.toString() ?? "");
  return (
    <form onSubmit={(e) => { e.preventDefault();
      onSubmit({ activity_level: act, target_weight_kg: tw ? +tw : null, timeframe_weeks: tf ? +tf : null },
        `${ACTIVITY.find((a) => a.value === act)!.label.split(" — ")[0]}${tw ? `, target ${tw} kg in ${tf || "?"} wk` : ""}.`); }}>
      <Labeled label="Activity level">
        <select className={inputCls} value={act} onChange={(e) => setAct(e.target.value as ActivityLevel)}>
          {ACTIVITY.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
        </select>
      </Labeled>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <Labeled label="Goal weight (kg, optional)"><input type="number" className={inputCls} value={tw} onChange={(e) => setTw(e.target.value)} /></Labeled>
        <Labeled label="Timeframe (weeks, optional)"><input type="number" className={inputCls} value={tf} onChange={(e) => setTf(e.target.value)} /></Labeled>
      </div>
      <Actions onBack={onBack} />
    </form>
  );
}

function HealthStep({ draft, onSubmit, onBack }: { draft: UserProfile; onSubmit: Sub; onBack: () => void }) {
  const [conds, setConds] = useState<string[]>(draft.medical_conditions);
  const [allergies, setAllergies] = useState<string[]>(draft.allergies);
  return (
    <form onSubmit={(e) => { e.preventDefault();
      onSubmit({ medical_conditions: conds, allergies },
        conds.length || allergies.length
          ? `Conditions: ${conds.join(", ") || "none"}. Allergies: ${allergies.join(", ") || "none"}.`
          : "No conditions or allergies."); }}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Labeled label="Medical conditions / injuries">
          <Chips values={conds} onChange={setConds} placeholder="type + Enter (e.g. knee injury)"
            suggestions={["knee injury", "hypertension", "diabetes", "back pain"]} />
        </Labeled>
        <Labeled label="Allergies">
          <Chips values={allergies} onChange={setAllergies} placeholder="type + Enter (e.g. peanuts)"
            suggestions={["peanuts", "lactose", "gluten", "shellfish"]} />
        </Labeled>
      </div>
      <Actions onBack={onBack} />
    </form>
  );
}

function FoodStep({ draft, onSubmit, onBack }: { draft: UserProfile; onSubmit: Sub; onBack: () => void }) {
  const [diet, setDiet] = useState(draft.diet_preference ?? "no preference");
  const [dislikes, setDislikes] = useState<string[]>(draft.disliked_foods);
  return (
    <form onSubmit={(e) => { e.preventDefault();
      onSubmit({ diet_preference: diet, disliked_foods: dislikes },
        `Diet: ${diet}${dislikes.length ? `; dislikes ${dislikes.join(", ")}` : ""}.`); }}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Labeled label="Diet preference">
          <select className={inputCls} value={diet} onChange={(e) => setDiet(e.target.value)}>
            {DIETS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </Labeled>
        <Labeled label="Foods you dislike">
          <Chips values={dislikes} onChange={setDislikes} placeholder="type + Enter (e.g. mushroom)"
            suggestions={["mushroom", "broccoli", "tofu"]} />
        </Labeled>
      </div>
      <Actions onBack={onBack} />
    </form>
  );
}

function BudgetStep({ draft, onSubmit, onBack }: { draft: UserProfile; onSubmit: Sub; onBack: () => void }) {
  const [budget, setBudget] = useState(draft.budget_weekly);
  const [cur, setCur] = useState(draft.currency);
  return (
    <form onSubmit={(e) => { e.preventDefault();
      onSubmit({ budget_weekly: budget, currency: cur }, `Budget: ${cur} ${budget}/week.`); }}>
      <div className="grid grid-cols-2 gap-3">
        <Labeled label="Weekly budget"><input type="number" className={inputCls} value={budget} onChange={(e) => setBudget(+e.target.value)} /></Labeled>
        <Labeled label="Currency">
          <select className={inputCls} value={cur} onChange={(e) => setCur(e.target.value)}>
            {["INR", "USD", "EUR", "GBP"].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </Labeled>
      </div>
      <Actions onBack={onBack} disabled={!budget} />
    </form>
  );
}

function TrainingStep({ draft, onSubmit, onBack }: { draft: UserProfile; onSubmit: Sub; onBack: () => void }) {
  const [days, setDays] = useState(draft.days_per_week ?? 4);
  const [mins, setMins] = useState(draft.session_minutes ?? 45);
  const [equip, setEquip] = useState<string[]>(draft.equipment_access);
  return (
    <form onSubmit={(e) => { e.preventDefault();
      onSubmit({ days_per_week: days, session_minutes: mins, equipment_access: equip },
        `${days} days/week × ${mins} min; equipment: ${equip.join(", ") || "bodyweight"}.`); }}>
      <div className="grid grid-cols-2 gap-3">
        <Labeled label="Days / week"><input type="number" className={inputCls} value={days} onChange={(e) => setDays(+e.target.value)} /></Labeled>
        <Labeled label="Minutes / session"><input type="number" className={inputCls} value={mins} onChange={(e) => setMins(+e.target.value)} /></Labeled>
      </div>
      <div className="mt-3">
        <Labeled label="Equipment available">
          <Chips values={equip} onChange={setEquip} placeholder="type + Enter" suggestions={EQUIPMENT} />
        </Labeled>
      </div>
      <Actions onBack={onBack} label="Review" />
    </form>
  );
}

function ReviewStep({ draft, onComplete, onBack }: { draft: UserProfile; onComplete: (p: UserProfile) => void; onBack: () => void }) {
  const rows: [string, string][] = [
    ["Goal", draft.goal.replace("_", " ")],
    ["You", `${draft.sex}, ${draft.age}y, ${draft.height_cm}cm, ${draft.weight_kg}kg, ${draft.activity_level}`],
    ["Medical", [...draft.medical_conditions, ...draft.allergies.map((a) => `allergy: ${a}`)].join(", ") || "none"],
    ["Diet", `${draft.diet_preference}${draft.disliked_foods.length ? ` (no ${draft.disliked_foods.join(", ")})` : ""}`],
    ["Budget", `${draft.currency} ${draft.budget_weekly}/week`],
    ["Training", `${draft.days_per_week}d × ${draft.session_minutes}min · ${draft.equipment_access.join(", ") || "bodyweight"}`],
  ];
  return (
    <div>
      <div className="grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="flex gap-2">
            <span className="w-16 shrink-0 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{k}</span>
            <span className="text-slate-200">{v}</span>
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-center justify-between">
        <button onClick={onBack} className={ghost}>Back</button>
        <button onClick={() => onComplete(draft)} className={`${primary} text-base`}>⚡ Start the multi-agent debate</button>
      </div>
    </div>
  );
}
