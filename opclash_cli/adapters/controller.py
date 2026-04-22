import requests
from urllib.parse import quote

from opclash_cli.local_config import load_config


class ControllerClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._config = load_config().controller
        self._session = session or requests.Session()

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._config.secret}"}

    def get_configs(self) -> dict:
        response = self._session.get(f"{self._config.url}/configs", headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_proxies(self) -> dict:
        response = self._session.get(f"{self._config.url}/proxies", headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_providers(self) -> dict:
        response = self._session.get(f"{self._config.url}/providers/proxies", headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def switch_proxy(self, group: str, target: str) -> dict:
        response = self._session.put(
            f"{self._config.url}/proxies/{group}",
            headers=self.headers,
            json={"name": target},
            timeout=10,
        )
        response.raise_for_status()
        if response.status_code == 204 or not getattr(response, "text", ""):
            return {}
        return response.json()

    def proxy_delay(self, name: str, test_url: str, timeout_ms: int) -> dict:
        response = self._session.get(
            f"{self._config.url}/proxies/{quote(name, safe='')}/delay",
            headers=self.headers,
            params={"url": test_url, "timeout": timeout_ms},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
