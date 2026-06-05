import { NextResponse } from "next/server";
import { createSupabaseAdminClient } from "@/lib/supabase/admin";
import { createSupabaseServerClient } from "@/lib/supabase/server";

function jsonError(status: number, errorCode: string, message: string) {
  return NextResponse.json(
    {
      success: false,
      error_code: errorCode,
      message
    },
    { status }
  );
}

export async function DELETE() {
  const sessionClient = createSupabaseServerClient();

  if (!sessionClient) {
    return jsonError(503, "auth_not_configured", "Supabase auth is not configured.");
  }

  const {
    data: { user },
    error: userError
  } = await sessionClient.auth.getUser();

  if (userError || !user) {
    return jsonError(401, "not_authenticated", "A signed-in user is required.");
  }

  const adminClient = createSupabaseAdminClient();

  if (!adminClient) {
    return jsonError(503, "account_delete_not_configured", "Supabase service role key is not configured.");
  }

  const { error: profileError } = await adminClient.from("profiles").delete().eq("user_id", user.id);

  if (profileError) {
    return jsonError(502, "profile_delete_failed", "Failed to delete profile data.");
  }

  const { error: deleteError } = await adminClient.auth.admin.deleteUser(user.id);

  if (deleteError) {
    return jsonError(502, "auth_delete_failed", "Failed to delete auth user.");
  }

  await sessionClient.auth.signOut().catch(() => {
    // The client performs a local sign-out after success as well.
  });

  return NextResponse.json({ success: true });
}
