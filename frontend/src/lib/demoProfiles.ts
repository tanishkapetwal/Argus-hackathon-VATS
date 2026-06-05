// Seeded demo profiles (build-plan 7.1). Each exercises a distinct path through the agent debate
// so the trace view tells a different story. The first is the conflict-forcing profile from
// docs/trace-view.md §4 (used for the 90-second demo narrative).

import type { UserProfile } from "./types";

export interface DemoProfile {
  id: string;
  label: string;
  description: string;
  profile: UserProfile;
}

// 1) Forces the full debate: medical caps + an over-budget high-protein diet → refinement round.
export const CONFLICT_PROFILE: UserProfile = {
  age: 34, sex: "male", height_cm: 178, weight_kg: 92, activity_level: "light",
  goal: "fat_loss", target_weight_kg: 78, timeframe_weeks: 12,
  medical_conditions: ["knee injury", "hypertension"], medications: [], allergies: ["peanuts"],
  budget_weekly: 1500, currency: "INR", diet_preference: "high protein, vegetarian",
  disliked_foods: ["mushroom"], equipment_access: ["dumbbells"],
  days_per_week: 4, session_minutes: 45, notes: "wants visible results fast",
};

// 2) Comfortable budget, no injuries → the plan fits first time; the Critic approves, no loop.
export const CLEAN_PROFILE: UserProfile = {
  age: 32, sex: "male", height_cm: 176, weight_kg: 72, activity_level: "light",
  goal: "general_health", target_weight_kg: 72, timeframe_weeks: 16,
  medical_conditions: [], medications: [], allergies: [],
  budget_weekly: 4000, currency: "INR", diet_preference: "balanced, vegetarian",
  disliked_foods: [], equipment_access: ["dumbbells"],
  days_per_week: 4, session_minutes: 45, notes: "steady, sustainable habits",
};

// 3) A red-flag symptom → the Medical Risk gate escalates and the Resolver refuses to optimize.
export const RED_FLAG_PROFILE: UserProfile = {
  age: 58, sex: "male", height_cm: 174, weight_kg: 95, activity_level: "sedentary",
  goal: "fat_loss", target_weight_kg: 82, timeframe_weeks: 16,
  medical_conditions: ["chest pain", "uncontrolled hypertension"], medications: ["amlodipine"],
  allergies: [], budget_weekly: 5000, currency: "INR", diet_preference: "vegetarian",
  disliked_foods: [], equipment_access: ["dumbbells"],
  days_per_week: 3, session_minutes: 40, notes: "new to exercise",
};

export const DEMO_PROFILES: DemoProfile[] = [
  {
    id: "conflict",
    label: "Conflict & refinement",
    description:
      "Aggressive fat-loss + knee injury + hypertension + tight ₹1500 budget + high-protein veg. " +
      "Budget overrun forces a refinement round that converges.",
    profile: CONFLICT_PROFILE,
  },
  {
    id: "clean",
    label: "Comfortable budget (clean pass)",
    description:
      "General-health goal, no injuries, generous budget. The plan fits first time, so the " +
      "Critic approves with no refinement loop.",
    profile: CLEAN_PROFILE,
  },
  {
    id: "redflag",
    label: "Red flag → referral",
    description:
      "Chest pain + uncontrolled hypertension. The Medical Risk gate escalates and the Resolver " +
      "returns a 'consult a professional first' plan instead of optimizing.",
    profile: RED_FLAG_PROFILE,
  },
];
