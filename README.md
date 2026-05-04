# GenLayer API Gateway
### Builder Contribution · Tools & Infrastructure

A secure, reusable Intelligent Contract library that lets any GenLayer dApp
call external APIs (crypto prices, weather, any JSON endpoint) without ever
exposing API keys on-chain or in transaction arguments.

---

## The Problem It Solves

GenLayer's Tools & Infrastructure category asks for:
> *"Libraries for Intelligent Contracts to interact with external APIs.
> Services that maintain API keys private while keeping security."*

Before this library, every developer had to either hard-code keys in their
contract (visible to anyone) or pass keys as transaction arguments (visible
in tx history). This contract stores keys privately in contract state,
never exposed through any public method.

---

## How It Works

```
Your dApp  →  ApiGateway contract  →  External API (prices, weather, etc.)
                    ↑
           API key stored privately
           in contract state only
```

- Keys registered by owner only, stored in `api_keys` TreeMap
- Callers must be approved by owner before they can fetch data  
- Per-service daily rate limits tracked on-chain
- All web fetches use `gl.eq_principle.strict_eq` for consensus safety
- LLM analysis via `gl.nondet.exec_prompt` with the Equivalence Principle

---

## Contract Methods

**Owner only:**
- `register_service(name, base_url, api_key, daily_limit)` — add a service
- `approve_caller(caller)` — whitelist an address
- `revoke_caller(caller)` — remove access
- `toggle_service(name, enabled)` — enable/disable a service
- `reset_counts()` — reset daily call counters

**Approved callers:**
- `fetch_price(coin_id)` — get crypto price from CoinGecko
- `fetch_webpage(service_name, path)` — fetch any registered endpoint
- `ask_about_data(service_name, path, question)` — LLM analysis of live data

**Anyone (view):**
- `get_service(name)` — public metadata (no key exposed)
- `list_services()` — list all registered services
- `is_approved(caller)` — check if an address has access

---

## Quickstart (GenLayer Studio)

1. Open **studio.genlayer.com**
2. Paste `api_gateway_final.py` into a new contract
3. Deploy with your wallet address as `owner`
4. Call `register_service` with:
   - name: `prices`
   - base_url: `https://api.coingecko.com/api/v3`
   - api_key: *(leave empty — CoinGecko free tier needs none)*
   - daily_limit: `100`
5. Call `fetch_price` with `bitcoin`

---

## Security Design

| Risk | Protection |
|---|---|
| API key leaking | Keys in private TreeMap, no view method exposes them |
| Unauthorized calls | Approved-caller whitelist enforced on every fetch |
| Abuse / overuse | Per-service daily call counter with configurable limit |
| Consensus attacks | Every web call wrapped in `gl.eq_principle.strict_eq` |

---

## Contribution Details

- **Type**: Builder → Tools & Infrastructure  
- **Date**: 2026-05-04  
- **SDK**: `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`
