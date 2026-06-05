"use client";

import { buildAppUserProfile, type AppUserProfile } from "./user-profile";

export type AppUserAccess = {
  profile: AppUserProfile | null;
  isAdmin: boolean;
};

async function getSupabaseClient() {
  const { createSupabaseBrowserClient } = await import("./supabase/browser");
  return createSupabaseBrowserClient();
}

export async function getCurrentAppUserProfile(): Promise<AppUserProfile | null> {
  const supabase = await getSupabaseClient();

  if (!supabase) {
    return null;
  }

  const {
    data: { user }
  } = await supabase.auth.getUser();

  return buildAppUserProfile(user);
}

export async function getCurrentAppUserAccess(): Promise<AppUserAccess> {
  const supabase = await getSupabaseClient();

  if (!supabase) {
    return { profile: null, isAdmin: false };
  }

  const {
    data: { user }
  } = await supabase.auth.getUser();
  const profile = buildAppUserProfile(user);

  if (!user) {
    return { profile, isAdmin: false };
  }

  const { data, error } = await supabase
    .from("admin_users")
    .select("user_id")
    .eq("user_id", user.id)
    .eq("active", true)
    .maybeSingle();

  return { profile, isAdmin: Boolean(data && !error) };
}

export async function signOutAppUser(): Promise<void> {
  const supabase = await getSupabaseClient();
  await supabase?.auth.signOut();
}
