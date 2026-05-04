# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from dataclasses import dataclass
import json


@allow_storage
@dataclass
class ServiceConfig:
    base_url: str
    key_label: str
    enabled: bool
    calls_today: u256
    daily_limit: u256


class ApiGateway(gl.Contract):
    owner: str
    services: TreeMap[str, ServiceConfig]
    api_keys: TreeMap[str, str]
    approved: TreeMap[str, bool]

    def __init__(self, owner: str) -> None:
        self.owner = owner
        self.services = TreeMap()
        self.api_keys = TreeMap()
        self.approved = TreeMap()

    def _check_owner(self) -> None:
        if str(gl.message.sender_address) != self.owner:
            raise Exception("Only owner can call this")

    def _check_approved(self) -> None:
        caller = str(gl.message.sender_address)
        if caller != self.owner and not self.approved.get(caller, False):
            raise Exception("Caller not approved")

    @gl.public.write
    def register_service(
        self,
        name: str,
        base_url: str,
        api_key: str,
        daily_limit: u256,
    ) -> None:
        self._check_owner()
        label = "k_" + name
        cfg = ServiceConfig(
            base_url=base_url,
            key_label=label,
            enabled=True,
            calls_today=u256(0),
            daily_limit=daily_limit,
        )
        self.services[name] = cfg
        self.api_keys[label] = api_key

    @gl.public.write
    def approve_caller(self, caller: str) -> None:
        self._check_owner()
        self.approved[caller] = True

    @gl.public.write
    def revoke_caller(self, caller: str) -> None:
        self._check_owner()
        self.approved[caller] = False

    @gl.public.write
    def toggle_service(self, name: str, enabled: bool) -> None:
        self._check_owner()
        cfg = self.services[name]
        cfg.enabled = enabled
        self.services[name] = cfg

    @gl.public.write
    def reset_counts(self) -> None:
        self._check_owner()
        for name in self.services:
            cfg = self.services[name]
            cfg.calls_today = u256(0)
            self.services[name] = cfg

    @gl.public.write
    def fetch_price(self, coin_id: str) -> str:
        self._check_approved()
        name = "prices"
        if name not in self.services:
            return json.dumps({"error": "prices service not registered"})
        cfg = self.services[name]
        if not cfg.enabled:
            return json.dumps({"error": "service disabled"})
        if cfg.calls_today >= cfg.daily_limit:
            return json.dumps({"error": "daily limit reached"})
        url = cfg.base_url + "/simple/price?ids=" + coin_id + "&vs_currencies=usd"

        def do_fetch() -> str:
            result = gl.nondet.web.get_webpage(url, mode="text")
            return result

        raw = gl.eq_principle.strict_eq(do_fetch)
        cfg.calls_today = cfg.calls_today + u256(1)
        self.services[name] = cfg
        return raw

    @gl.public.write
    def fetch_webpage(self, service_name: str, path: str) -> str:
        self._check_approved()
        if service_name not in self.services:
            return json.dumps({"error": "unknown service"})
        cfg = self.services[service_name]
        if not cfg.enabled:
            return json.dumps({"error": "service disabled"})
        if cfg.calls_today >= cfg.daily_limit:
            return json.dumps({"error": "daily limit reached"})
        key = self.api_keys.get(cfg.key_label, "")
        sep = "&" if "?" in path else "?"
        url = cfg.base_url + path
        if key:
            url = url + sep + "appid=" + key

        def do_fetch() -> str:
            return gl.nondet.web.get_webpage(url, mode="text")

        raw = gl.eq_principle.strict_eq(do_fetch)
        cfg.calls_today = cfg.calls_today + u256(1)
        self.services[service_name] = cfg
        return raw

    @gl.public.write
    def ask_about_data(self, service_name: str, path: str, question: str) -> str:
        self._check_approved()
        if service_name not in self.services:
            return "unknown service"
        cfg = self.services[service_name]
        if not cfg.enabled:
            return "service disabled"
        key = self.api_keys.get(cfg.key_label, "")
        sep = "&" if "?" in path else "?"
        url = cfg.base_url + path
        if key:
            url = url + sep + "appid=" + key

        def do_ask() -> str:
            data = gl.nondet.web.get_webpage(url, mode="text")
            prompt = (
                "You are a data assistant. "
                "Here is data from an API:\n\n"
                + data
                + "\n\nAnswer this question based only on the data above. "
                "Be brief and precise.\n\nQuestion: "
                + question
            )
            result = gl.nondet.exec_prompt(prompt)
            return result

        answer = gl.eq_principle.strict_eq(do_ask)
        return answer

    @gl.public.view
    def get_service(self, name: str) -> str:
        if name not in self.services:
            return json.dumps({"error": "not found"})
        cfg = self.services[name]
        return json.dumps({
            "base_url": cfg.base_url,
            "enabled": cfg.enabled,
            "calls_today": int(cfg.calls_today),
            "daily_limit": int(cfg.daily_limit),
        })

    @gl.public.view
    def list_services(self) -> str:
        names = []
        for name in self.services:
            names.append(name)
        return json.dumps(names)

    @gl.public.view
    def is_approved(self, caller: str) -> bool:
        return self.approved.get(caller, False)
