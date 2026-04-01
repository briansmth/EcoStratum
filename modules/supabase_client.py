"""
Supabase client: authentication and search history persistence.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_url = os.environ.get("SUPABASE_URL", "")
_key = os.environ.get("SUPABASE_KEY", "")

supabase: Client = create_client(_url, _key) if _url and _key else None


# ── Auth ────────────────────────────────────────────────────────────────────


def sign_up(email: str, password: str):
    resp = supabase.auth.sign_up({"email": email, "password": password})
    if resp.user is None:
        raise Exception("Sign-up failed. Please check your credentials.")
    return resp


def sign_in(email: str, password: str):
    resp = supabase.auth.sign_in_with_password(
        {"email": email, "password": password}
    )
    if resp.user is None:
        raise Exception("Invalid email or password.")
    return resp


def sign_out():
    supabase.auth.sign_out()


def get_current_user():
    resp = supabase.auth.get_user()
    return resp.user if resp else None


# ── Search history ──────────────────────────────────────────────────────────


def save_search(user_id: str, lat: float, lon: float, radius_km: int):
    supabase.table("search_history").insert({
        "user_id": user_id,
        "lat": lat,
        "lon": lon,
        "radius_km": radius_km,
    }).execute()


def get_search_history(user_id: str, limit: int = 20) -> list:
    resp = (
        supabase.table("search_history")
        .select("lat, lon, radius_km, searched_at")
        .eq("user_id", user_id)
        .order("searched_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []
