// TypeScript mirror of the backend Pydantic schemas (../docs/data-models.md).
// Keep in sync with backend/app/schemas/models.py — they are the same contract.

export type Sex = "male" | "female" | "other";
export type ActivityLevel =
  | "sedentary" | "light" | "moderate" | "active" | "very_active";
export type Goal =
  | "fat_loss" | "muscle_gain" | "maintenance" | "general_health" | "endurance";
export type Severity = "info" | "caution" | "hard_limit" | "red_flag";

export type ConflictType =
  | "MEDICAL_VIOLATION" | "ENERGY_IMBALANCE" | "BUDGET_OVERRUN"
  | "MACRO_INCOHERENCE" | "RECOVERY_RISK" | "MISSING_DISCLAIMER";

export type TraceEventType =
  | "RUN_STARTED" | "ROUND_STARTED" | "AGENT_STARTED" | "AGENT_INPUT"
  | "AGENT_OUTPUT" | "TOOL_CALLED" | "MESSAGE_SENT" | "CONFLICT_RAISED"
  | "REVISION_REQUESTED" | "AGENT_COMPLETED" | "RUN_COMPLETED" | "ERROR";

export interface UserProfile {
  age: number;
  sex: Sex;
  height_cm: number;
  weight_kg: number;
  activity_level: ActivityLevel;
  goal: Goal;
  target_weight_kg?: number | null;
  timeframe_weeks?: number | null;
  medical_conditions: string[];
  medications: string[];
  allergies: string[];
  budget_weekly: number;
  currency: string;
  diet_preference?: string | null;
  disliked_foods: string[];
  equipment_access: string[];
  days_per_week?: number | null;
  session_minutes?: number | null;
  notes?: string | null;
}

export interface MedicalFlag {
  condition: string; severity: Severity; rationale: string; source?: string | null;
}
export interface MedicalConstraints {
  max_added_sugar_g?: number | null;
  max_sodium_mg?: number | null;
  max_saturated_fat_g?: number | null;
  min_protein_g_per_kg?: number | null;
  excluded_foods: string[];
  required_nutrients: string[];
  forbidden_movements: string[];
  max_intensity?: string | null;
  requires_warmup: boolean;
  max_heart_rate_pct?: number | null;
  requires_professional: boolean;
  flags: MedicalFlag[];
  required_disclaimers: string[];
}

export interface MacroTargets {
  bmr_kcal: number; tdee_kcal: number; target_kcal: number;
  protein_g: number; carbs_g: number; fat_g: number; fiber_g?: number | null;
  rationale: string;
}
export interface FoodItem {
  name: string; quantity: string; kcal: number;
  protein_g: number; carbs_g: number; fat_g: number; fdc_id?: number | null;
}
export interface Meal {
  name: string; items: FoodItem[];
  kcal: number; protein_g: number; carbs_g: number; fat_g: number;
}
export interface NutritionPlan {
  macros: MacroTargets;
  daily_meals: Meal[];
  weekly_grocery_list: FoodItem[];
  supplements: string[];
  satisfies_constraints: boolean;
  constraint_notes: string[];
  assumptions: string[];
}

export interface Exercise {
  name: string; sets?: number | null; reps?: string | null;
  duration_min?: number | null; intensity?: string | null; notes?: string | null;
}
export interface WorkoutDay {
  day_label: string; focus: string; exercises: Exercise[]; est_kcal_burn: number;
}
export interface FitnessPlan {
  weekly_schedule: WorkoutDay[];
  days_per_week: number;
  est_weekly_kcal_burn: number;
  equipment_needed: string[];
  progression: string;
  satisfies_constraints: boolean;
  constraint_notes: string[];
  assumptions: string[];
}

export interface RevisionRequest {
  target_agent: string; reason: string; constraint: string; raised_by: string;
}
export interface CostLine {
  item: string; category: string; weekly_cost: number; source: string;
}
export interface BudgetReport {
  currency: string;
  weekly_budget: number;
  estimated_weekly_cost: number;
  breakdown: CostLine[];
  within_budget: boolean;
  overrun: number;
  suggested_cuts: string[];
  revision_requests: RevisionRequest[];
  notes: string[];
}

export interface Conflict {
  type: ConflictType; severity: Severity; description: string; evidence: string;
  target_agents: string[]; suggested_fix?: string | null;
}
export interface Critique {
  conflicts: Conflict[]; overall_assessment: string; approved: boolean;
}

export interface AgentMessage {
  sender: string; recipient: string; intent: string;
  payload: Record<string, unknown>; text: string;
}

export interface AgentContribution {
  agent: string; summary: string; changed_due_to: string[];
}
export interface HealthPlan {
  profile: UserProfile;
  constraints: MedicalConstraints;
  nutrition: NutritionPlan;
  fitness: FitnessPlan;
  budget: BudgetReport;
  summary: string;
  rationale: string;
  resolved_conflicts: Conflict[];
  open_tradeoffs: string[];
  agent_contributions: AgentContribution[];
  requires_professional: boolean;
  disclaimers: string[];
  generated_at: string;
}

export interface TraceEvent {
  run_id: string;
  seq: number;
  type: TraceEventType;
  agent?: string | null;
  round: number;
  timestamp: string;
  summary: string;
  payload: Record<string, unknown>;
}
