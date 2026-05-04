# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json


class ApiGateway(gl.Contract):
    owner: str
    store: TreeMap[str, str]

    def __init__(self, owner: str) -> None:
        self.owner = owner
        self.store = TreeMap()

    def _check_owner(self) -> None:
        if str(gl.message.sender_address) != self.owner:
            raise Exception("Only owner allowed")

    def _check_approved(self) -> None:
        caller = str(gl.message.sender_address)
        if caller == self.owner:
            return
        if self.store.get("approved:" + caller, "false") != "true":
            raise Exception("Caller not approved")

    @gl.public.write
    def register_service(
        self,
        name: str,
        base_url: str,
        api_key: str,
        daily_limit: str,
    ) -> None:
        self._check_owner()
        self.store["svc:" + name + ":url"] = base_url
        self.store["svc:" + name + ":key"] = api_key
        self.store["svc:" + name + ":enabled"] = "true"
        self.store["svc:" + name + ":calls"] = "0"
        self.store["svc:" + name + ":limit"] = daily_limit

    @gl.public.write
    def approve_caller(self, caller: str) -> None:
        self._check_owner()
        self.store["approved:" + caller] = "true"

    @gl.public.write
    def revoke_caller(self, caller: str) -> None:
        self._check_owner()
        self.store["approved:" + caller] = "false"

    @gl.public.write
    def disable_service(self, name: str) -> None:
        self._check_owner()
        self.store["svc:" + name + ":enabled"] = "false"

    @gl.public.write
    def enable_service(self, name: str) -> None:
        self._check_owner()
        self.store["svc:" + name + ":enabled"] = "true"

    @gl.public.write
    def fetch_price(self, coin_id: str) -> str:
        self._check_approved()
        name = "prices"
        url = self.store.get("svc:" + name + ":url", "")
        if url == "":
            return json.dumps({"error": "prices service not registered"})
        if self.store.get("svc:" + name + ":enabled", "false") != "true":
            return json.dumps({"error": "service disabled"})
        calls = int(self.store.get("svc:" + name + ":calls", "0"))
        limit = int(self.store.get("svc:" + name + ":limit", "0"))
        if calls >= limit:
            return json.dumps({"error": "daily limit reached"})
        full_url = url + "/simple/price?ids=" + coin_id + "&vs_currencies=usd"

        def do_fetch() -> str:
            return gl.nondet.web.get_webpage(full_url, mode="text")

        raw = gl.eq_principle.strict_eq(do_fetch)
        self.store["svc:" + name + ":calls"] = str(calls + 1)
        return raw

    @gl.public.write
    def fetch_data(self, service_name: str, path: str) -> str:
        self._check_approved()
        url = self.store.get("svc:" + service_name + ":url", "")
        if url == "":
            return json.dumps({"error": "service not found"})
        if self.store.get("svc:" + service_name + ":enabled", "false") != "true":
            return json.dumps({"error": "service disabled"})
        calls = int(self.store.get("svc:" + service_name + ":calls", "0"))
        limit = int(self.store.get("svc:" + service_name + ":limit", "0"))
        if calls >= limit:
            return json.dumps({"error": "daily limit reached"})
        key = self.store.get("svc:" + service_name + ":key", "")
        sep = "&" if "?" in path else "?"
        full_url = url + path
        if key != "":
            full_url = full_url + sep + "appid=" + key

        def do_fetch() -> str:
            return gl.nondet.web.get_webpage(full_url, mode="text")

        raw = gl.eq_principle.strict_eq(do_fetch)
        self.store["svc:" + service_name + ":calls"] = str(calls + 1)
        return raw

    @gl.public.write
    def ask_about_data(self, service_name: str, path: str, question: str) -> str:
        self._check_approved()
        url = self.store.get("svc:" + service_name + ":url", "")
        if url == "":
            return "service not found"
        if self.store.get("svc:" + service_name + ":enabled", "false") != "true":
            return "service disabled"
        key = self.store.get("svc:" + service_name + ":key", "")
        sep = "&" if "?" in path else "?"
        full_url = url + path
        if key != "":
            full_url = full_url + sep + "appid=" + key

        def do_ask() -> str:
            data = gl.nondet.web.get_webpage(full_url, mode="text")
            prompt = (
                "You are a data assistant for a blockchain contract. "
                "Here is live data from an API:\n\n"
                + data
                + "\n\nAnswer this question using only the data above. "
                "Be brief and precise.\n\nQuestion: "
                + question
            )
            return gl.nondet.exec_prompt(prompt)

        return gl.eq_principle.strict_eq(do_ask)

    @gl.public.view
    def get_service(self, name: str) -> str:
        url = self.store.get("svc:" + name + ":url", "")
        if url == "":
            return json.dumps({"error": "not found"})
        return json.dumps({
            "base_url": url,
            "enabled": self.store.get("svc:" + name + ":enabled", "false"),
            "calls_today": self.store.get("svc:" + name + ":calls", "0"),
            "daily_limit": self.store.get("svc:" + name + ":limit", "0"),
        })

    @gl.public.view
    def is_approved(self, caller: str) -> bool:
        return self.store.get("approved:" + caller, "false") == "true"

    @gl.public.view
    def get_owner(self) -> str:
        return self.owner
