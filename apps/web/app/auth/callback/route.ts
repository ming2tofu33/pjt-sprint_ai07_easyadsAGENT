import { NextResponse } from "next/server";
import { getSafeAuthRedirectPath } from "@/lib/auth-navigation";
import { getDisplayNameFromUser } from "@/lib/user-profile";
import { createSupabaseServerClient } from "@/lib/supabase/server";

function buildLoginUrl(origin: string, nextPath: string, error: string): URL {
  const path = nextPath.startsWith("/admin") ? "/admin/login" : "/login";
  const loginUrl = new URL(path, origin);
  loginUrl.searchParams.set("next", nextPath);
  loginUrl.searchParams.set("error", error);
  return loginUrl;
}

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get("code");
  const nextPath = getSafeAuthRedirectPath(requestUrl.searchParams.get("next"));

  if (!code) {
    return NextResponse.redirect(buildLoginUrl(requestUrl.origin, nextPath, "missing_code"));
  }

  const supabase = createSupabaseServerClient();

  if (!supabase) {
    return NextResponse.redirect(buildLoginUrl(requestUrl.origin, nextPath, "missing_env"));
  }

  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    return NextResponse.redirect(buildLoginUrl(requestUrl.origin, nextPath, "auth_failed"));
  }

  const {
    data: { user }
  } = await supabase.auth.getUser();

  if (user) {
    await supabase.from("profiles").upsert(
      {
        user_id: user.id,
        email: user.email ?? null,
        display_name: getDisplayNameFromUser(user),
        metadata: {
          account_type: user.is_anonymous ? "guest" : "user",
          avatar_url: user.user_metadata?.avatar_url ?? user.user_metadata?.picture ?? null,
          provider: user.app_metadata?.provider ?? user.identities?.[0]?.provider ?? null
        },
        updated_at: new Date().toISOString()
      },
      { onConflict: "user_id" }
    );
  }

  return NextResponse.redirect(new URL(nextPath, requestUrl.origin));
}
