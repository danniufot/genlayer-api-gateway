# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
GenLayer API Gateway Library
============================
A reusable Tools & Infrastructure Intelligent Contract that allows other
contracts and dApps to securely call external APIs (weather, price feeds,
social media, etc.) without exposing API keys on-chain.

Key features:
  - Owner-only API key registration (keys are stored in contract state,
    never passed through public call arguments)
  - Per-service rate limiting stored on-chain
  - Consensus-safe non-deterministic web fetches wrapped with the
    Equivalence Principle
  - Public read methods for approved callers to request data

Contribution Type : Builder > Tools & Infrastructure
Author           : Daniel  (GenLayer Portal)
Date             : 2026-05-04
"""

from genlayer import *
import json


# ──────────────────────────────────────────────
# Data-class helpers
# ──────────────────────────────────────────────

@gl.dataclass
class ServiceConfig:
    """Registered external-API service entry."""
    base_url: str          # e.g. "https://api.openweathermap.org/data/2.5"
    api_key_env: str       # internal label for the stored key
    enabled: bool
    calls_today: u256
    daily_limit: u256


@gl.dataclass
class ApiResponse:
    """Structured result returned to callers."""
    success: bool
    data: str              # JSON string of the response payload
    service: str
    timestamp: u256


# ──────────────────────────────────────────────
# Main Contract
# ──────────────────────────────────────────────

class ApiGateway(gl.Contract):
    """
    Secure API Gateway for GenLayer Intelligent Contracts.

    Deployment args:
        owner (Address) — the account that can register / manage services.
    """

    # ── state ──────────────────────────────────
    owner: Address

    # service_name -> ServiceConfig
    services: TreeMap[str, ServiceConfig]

    # service_name -> api_key  (private; never exposed via view methods)
    _api_keys: TreeMap[str, str]

    # approved caller contracts -> bool
    approved_callers: TreeMap[Address, bool]

    # cumulative call log (caller -> count)
    call_counts: TreeMap[Address, u256]

    # ── constructor ────────────────────────────

    def __init__(self, owner: Address) -> None:
        self.owner = owner
        self.services = TreeMap()
        self._api_keys = TreeMap()
        self.approved_callers = TreeMap()
        self.call_counts = TreeMap()

    # ── internal guards ────────────────────────

    def _only_owner(self) -> None:
        if gl.message.sender_address != self.owner:
            raise gl.vm.UserError("ApiGateway: caller is not the owner")

    def _only_approved(self) -> None:
        caller = gl.message.sender_address
        if caller != self.owner and not self.approved_callers.get(caller, False):
            raise gl.vm.UserError("ApiGateway: caller is not approved")

    # ── admin write methods ────────────────────

    @gl.public.write
    def register_service(
        self,
        name: str,
        base_url: str,
        api_key: str,
        daily_limit: u256,
    ) -> None:
        """
        Register (or update) an external API service.
        Only the owner can call this — the api_key is stored privately.
        """
        self._only_owner()
        if not name or not base_url:
            raise gl.vm.UserError("ApiGateway: name and base_url are required")

        config = ServiceConfig(
            base_url=base_url,
            api_key_env=f"key_{name}",
            enabled=True,
            calls_today=u256(0),
            daily_limit=daily_limit,
        )
        self.services[name] = config
        self._api_keys[f"key_{name}"] = api_key

    @gl.public.write
    def disable_service(self, name: str) -> None:
        """Disable a registered service (owner only)."""
        self._only_owner()
        if name not in self.services:
            raise gl.vm.UserError(f"ApiGateway: unknown service '{name}'")
        svc = self.services[name]
        svc.enabled = False
        self.services[name] = svc

    @gl.public.write
    def enable_service(self, name: str) -> None:
        """Re-enable a previously disabled service (owner only)."""
        self._only_owner()
        if name not in self.services:
            raise gl.vm.UserError(f"ApiGateway: unknown service '{name}'")
        svc = self.services[name]
        svc.enabled = True
        self.services[name] = svc

    @gl.public.write
    def approve_caller(self, caller: Address) -> None:
        """Grant a contract address permission to use the gateway (owner only)."""
        self._only_owner()
        self.approved_callers[caller] = True

    @gl.public.write
    def revoke_caller(self, caller: Address) -> None:
        """Revoke a caller's gateway access (owner only)."""
        self._only_owner()
        self.approved_callers[caller] = False

    @gl.public.write
    def reset_daily_counts(self) -> None:
        """Reset all per-service daily call counters (owner only)."""
        self._only_owner()
        for name in self.services:
            svc = self.services[name]
            svc.calls_today = u256(0)
            self.services[name] = svc

    # ── public data-fetch methods ──────────────

    @gl.public.write
    def fetch_weather(self, city: str) -> ApiResponse:
        """
        Fetch current weather for a city via OpenWeatherMap.
        Uses GenLayer's non-deterministic web access wrapped in the
        Equivalence Principle so validators reach consensus on the result.

        Requires 'weather' service to be registered.
        """
        self._only_approved()
        return self._fetch_json_service(
            service_name="weather",
            endpoint=f"/weather?q={city}&units=metric",
        )

    @gl.public.write
    def fetch_crypto_price(self, symbol: str) -> ApiResponse:
        """
        Fetch the latest USD price for a crypto symbol (e.g. 'BTC', 'ETH').
        Requires 'coingecko' service to be registered.
        The CoinGecko free tier needs no key; register with an empty key.
        """
        self._only_approved()
        coin_id = symbol.lower()
        return self._fetch_json_service(
            service_name="coingecko",
            endpoint=f"/simple/price?ids={coin_id}&vs_currencies=usd",
        )

    @gl.public.write
    def fetch_custom(self, service_name: str, endpoint: str) -> ApiResponse:
        """
        Generic endpoint fetch for any registered service.
        `endpoint` is appended to the service's base_url.
        """
        self._only_approved()
        return self._fetch_json_service(service_name, endpoint)

    # ── LLM-assisted analysis ──────────────────

    @gl.public.write
    def analyze_api_data(
        self,
        service_name: str,
        endpoint: str,
        question: str,
    ) -> str:
        """
        Fetch data from a registered service and pass it to the LLM
        with a natural-language `question`.  Returns the LLM's answer as
        a plain string.  Uses the Equivalence Principle for consensus.
        """
        self._only_approved()

        raw = self._fetch_json_service(service_name, endpoint)
        if not raw.success:
            return f"Error fetching data: {raw.data}"

        prompt = f"""
You are a helpful data analyst for a blockchain smart contract.

Here is live JSON data retrieved from the '{service_name}' API:

{raw.data}

Answer the following question based solely on the data above.
Be concise and precise. If the answer is a number, return only the number.

Question: {question}
"""
        def leader_fn() -> str:
            return gl.nondet.exec_prompt(prompt)

        def validator_fn(leaders_res) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            # Validators use LLM to assess semantic equivalence
            check_prompt = f"""
Two AI validators each answered this question from API data:
Question: {question}

Answer A: {leaders_res.calldata}
Answer B: {leader_fn()}

Are both answers semantically equivalent (same meaning / same numeric value)?
Respond with exactly one word: YES or NO
"""
            verdict = gl.nondet.exec_prompt(check_prompt).strip().upper()
            return verdict == "YES"

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    # ── view methods ───────────────────────────

    @gl.public.view
    def get_service_info(self, name: str) -> dict:
        """Return public metadata about a registered service (no key exposed)."""
        if name not in self.services:
            return {"error": f"Unknown service '{name}'"}
        svc = self.services[name]
        return {
            "base_url": svc.base_url,
            "enabled": svc.enabled,
            "calls_today": int(svc.calls_today),
            "daily_limit": int(svc.daily_limit),
        }

    @gl.public.view
    def list_services(self) -> list:
        """Return names of all registered services."""
        return [name for name in self.services]

    @gl.public.view
    def is_caller_approved(self, caller: Address) -> bool:
        """Check if a caller address has gateway access."""
        return self.approved_callers.get(caller, False)

    @gl.public.view
    def get_call_count(self, caller: Address) -> u256:
        """Return lifetime call count for a caller."""
        return self.call_counts.get(caller, u256(0))

    # ── internal helpers ───────────────────────

    def _fetch_json_service(
        self,
        service_name: str,
        endpoint: str,
    ) -> ApiResponse:
        """
        Core non-deterministic fetch wrapped with strict-equality equivalence.
        Builds the full URL, injects the API key as a query param, fetches,
        and stores the result.
        """
        if service_name not in self.services:
            return ApiResponse(
                success=False,
                data=json.dumps({"error": f"Unknown service '{service_name}'"}),
                service=service_name,
                timestamp=u256(0),
            )

        svc = self.services[service_name]

        if not svc.enabled:
            return ApiResponse(
                success=False,
                data=json.dumps({"error": "Service is disabled"}),
                service=service_name,
                timestamp=u256(0),
            )

        if svc.calls_today >= svc.daily_limit:
            return ApiResponse(
                success=False,
                data=json.dumps({"error": "Daily rate limit reached"}),
                service=service_name,
                timestamp=u256(0),
            )

        # Retrieve key privately (never surfaces via view)
        api_key = self._api_keys.get(svc.api_key_env, "")

        # Build URL — append key only if one exists
        sep = "&" if "?" in endpoint else "?"
        url = svc.base_url + endpoint
        if api_key:
            url = url + sep + f"appid={api_key}"

        # Non-deterministic block: fetch the live data
        def do_fetch() -> str:
            raw = gl.get_webpage(url, mode="text")
            # Validate it's parseable JSON
            try:
                json.loads(raw)
            except Exception:
                raise gl.vm.UserError("ApiGateway: response is not valid JSON")
            return raw

        fetched: str = gl.eq_principle_strict_eq(do_fetch)

        # Update counters
        svc.calls_today = svc.calls_today + u256(1)
        self.services[service_name] = svc

        caller = gl.message.sender_address
        self.call_counts[caller] = self.call_counts.get(caller, u256(0)) + u256(1)

        return ApiResponse(
            success=True,
            data=fetched,
            service=service_name,
            timestamp=u256(0),   # block timestamp not exposed in this SDK version
        )
