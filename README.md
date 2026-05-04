# GenLayer API Gateway — Tools & Infrastructure Library

> **Builder Contribution · Tools & Infrastructure · GenLayer Portal**  
> Estimated value: 50–2500 pts

---

## What This Is

A reusable **Intelligent Contract library** that gives any GenLayer dApp a
secure, rate-limited gateway to external REST APIs — weather, crypto prices,
social feeds, or anything with a JSON endpoint — **without ever exposing API
keys on-chain or in public call arguments**.

---

## The Problem It Solves

The GenLayer docs describe the Tools & Infrastructure category as:

> *"Create libraries for Intelligent Contracts to interact with external APIs
> like weather APIs, price feeds, and social media.  
> Create services needed in common patterns like maintaining API keys private
> while keeping security."*

Traditional approaches either:
- Hard-code keys in contract source (visible to anyone reading the chain), or  
- Pass keys as transaction arguments (visible in tx history), or  
- Route everything through a centralised off-chain proxy (defeats the point).

**ApiGateway** solves this by storing keys in the contract's private state
(`TreeMap[str, str]`), making them readable only by on-chain execution
— never by any public view method or read RPC call.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 YOUR dApp / CONTRACT                │
│  client.writeContract({ fn: "fetch_weather", ... }) │
└──────────────────────┬──────────────────────────────┘
                       │ (approved caller only)
┌──────────────────────▼──────────────────────────────┐
│              ApiGateway Intelligent Contract         │
│                                                     │
│  ┌─────────────┐   ┌──────────────┐                 │
│  │  _api_keys  │   │   services   │                 │
│  │  (private   │   │  (public     │                 │
│  │   TreeMap)  │   │   metadata)  │                 │
│  └──────┬──────┘   └──────┬───────┘                 │
│         │ key injected     │ config checked          │
│         └──────────────────┘                        │
│                    │                                │
│         gl.eq_principle_strict_eq(do_fetch)         │
│                    │  (non-deterministic block)     │
└──────────────────────────────────────────────────────┘
                       │ consensus via Optimistic Democracy
┌──────────────────────▼──────────────────────────────┐
│           External JSON API  (e.g. OpenWeatherMap)  │
└─────────────────────────────────────────────────────┘
```

---

## Contract API

### Write Methods (owner only)

| Method | Args | Description |
|---|---|---|
| `register_service` | name, base_url, api_key, daily_limit | Register / update a service |
| `disable_service` | name | Temporarily disable a service |
| `enable_service` | name | Re-enable a service |
| `approve_caller` | caller: Address | Grant a contract gateway access |
| `revoke_caller` | caller: Address | Revoke access |
| `reset_daily_counts` | — | Reset per-service daily counters |

### Write Methods (approved callers)

| Method | Args | Returns |
|---|---|---|
| `fetch_weather` | city: str | `ApiResponse` |
| `fetch_crypto_price` | symbol: str | `ApiResponse` |
| `fetch_custom` | service_name, endpoint | `ApiResponse` |
| `analyze_api_data` | service_name, endpoint, question | str (LLM answer) |

### View Methods (anyone)

| Method | Args | Returns |
|---|---|---|
| `get_service_info` | name | dict (no key!) |
| `list_services` | — | list[str] |
| `is_caller_approved` | caller | bool |
| `get_call_count` | caller | u256 |

---

## Security Properties

| Property | How achieved |
|---|---|
| **API keys never leak** | Stored in `_api_keys` TreeMap; no view exposes it |
| **Caller access control** | `approved_callers` whitelist; `_only_approved()` guard |
| **Owner-only admin** | `_only_owner()` guard on all registration methods |
| **Rate limiting** | `calls_today / daily_limit` check per service |
| **Consensus-safe fetches** | `gl.eq_principle_strict_eq` wraps every web call |
| **Prompt injection hardening** | LLM prompts are templated; user input never appended raw |

---

## Quickstart

### 1. Install tooling

```bash
npm install -g @genlayer/cli
genlayer init my-dapp
cd my-dapp
```

### 2. Copy the contract

```bash
cp path/to/api_gateway.py contracts/
```

### 3. Deploy

```bash
# Deploy to GenLayer Studio (local)
genlayer deploy --contract contracts/api_gateway.py \
  --args "0xYOUR_OWNER_ADDRESS"
```

### 4. Register a service (owner only)

```typescript
// genlayer-js
await client.writeContract({
  address: gatewayAddress,
  functionName: "register_service",
  args: [
    "weather",
    "https://api.openweathermap.org/data/2.5",
    "YOUR_OWM_API_KEY",        // stored privately on-chain
    100,                       // daily call limit
  ],
});
```

### 5. Approve your consuming contract

```typescript
await client.writeContract({
  address: gatewayAddress,
  functionName: "approve_caller",
  args: [myOtherContractAddress],
});
```

### 6. Fetch live weather from another contract

```python
# in your_other_contract.py
gateway = gl.get_contract(GATEWAY_ADDRESS)
result = gateway.fetch_weather("Lagos")
temp = json.loads(result.data)["main"]["temp"]
```

---

## Running Tests

```bash
pip install genlayer-test pytest
pytest tests/test_api_gateway.py -v
```

---

## Supported Services (out of the box)

| Service name | API | Key required? |
|---|---|---|
| `weather` | OpenWeatherMap `/weather` | Yes (free tier) |
| `coingecko` | CoinGecko `/simple/price` | No (free tier) |
| Any custom | Configurable via `register_service` | Optional |

---

## Contribution Details

- **Category**: Builder → Tools & Infrastructure  
- **Date**: 2026-05-04  
- **Contribution**: Reusable Intelligent Contract library + tests + documentation  
- **Notes**: Implements secure API key management, rate limiting, and
  LLM-assisted data analysis using the latest `py-genlayer` SDK.
  Fully testable with `genlayer-test` / `pytest`.
