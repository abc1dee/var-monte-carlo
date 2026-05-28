from supabase import create_client
from settings import settings

supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
user_id = "960f07b8-4489-41b3-9ba9-e814abf5838d"

# ── Test simulation_runs ──────────────────────────────────────────────
print("\n--- simulation_runs INSERT ---")
try:
    r = supabase.table("simulation_runs").insert({
        "user_id": user_id, "ticker": "AAPL", "horizon_days": 30,
        "confidence_level": 95, "num_simulations": 10000,
        "initial_investment": 100000, "var_pct": 0.05,
        "var_dollar": 5000, "cvar_pct": 0.07,
        "cvar_dollar": 7000, "current_price": 150.0
    }).execute()
    print("OK:", r.data)
except Exception as e:
    print(f"FAIL {type(e).__name__}: {e}")

print("\n--- simulation_runs SELECT ---")
try:
    r = supabase.table("simulation_runs").select("*").limit(1).execute()
    print("OK:", r.data)
except Exception as e:
    print(f"FAIL {type(e).__name__}: {e}")

# ── Test usage_counts ─────────────────────────────────────────────────
print("\n--- usage_counts INSERT ---")
try:
    r = supabase.table("usage_counts").insert({
        "user_id": user_id, "ip_address": "127.0.0.1"
    }).execute()
    print("OK:", r.data)
except Exception as e:
    print(f"FAIL {type(e).__name__}: {e}")

print("\n--- usage_counts SELECT ---")
try:
    r = supabase.table("usage_counts").select("id", count="exact").limit(1).execute()
    print("OK count:", r.count)
except Exception as e:
    print(f"FAIL {type(e).__name__}: {e}")
