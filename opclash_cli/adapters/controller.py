import requests
from urllib.parse import quote
from urllib.parse import urlparse

from opclash_cli.errors import CliError
from opclash_cli.local_config import load_config


class ControllerClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._config = load_config().controller
        self._session = session or requests.Session()

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._config.secret}"}

    @property
    def _base_url(self) -> str:
        raw = (self._config.url or "").strip()
        if not raw:
            raise CliError(
                "CONTROLLER_URL_MISSING",
                "Controller URL is not configured.",
                {
                    "guidance": "Run `opclash_cli init --controller-url <url> --controller-secret <secret>` first.",
                },
            )
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CliError(
                "CONTROLLER_URL_INVALID",
                "Controller URL is invalid.",
                {
                    "controller_url": raw,
                    "guidance": "Use an absolute URL such as http://127.0.0.1:9090.",
                },
            )
        return raw.rstrip("/")

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        try:
            response = self._session.request(
                method,
                f"{self._base_url}{path}",
                headers=self.headers,
                timeout=10,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            raise CliError(
                "CONTROLLER_REQUEST_FAILED",
                "Failed to reach Clash controller.",
                {
                    "controller_url": self._base_url,
                    "reason": error.__class__.__name__,
                    "detail": str(error),
                },
            ) from error

    def get_configs(self) -> dict:
        response = self._request("GET", "/configs")
        return response.json()

    def get_proxies(self) -> dict:
        response = self._request("GET", "/proxies")
        return response.json()

    def get_providers(self) -> dict:
        response = self._request("GET", "/providers/proxies")
        return response.json()

    def switch_proxy(self, group: str, target: str) -> dict:
        response = self._request(
            "PUT",
            f"/proxies/{group}",
            json={"name": target},
        )
        if response.status_code == 204 or not getattr(response, "text", ""):
            return {}
        return response.json()

    def proxy_delay(self, name: str, test_url: str, timeout_ms: int) -> dict:
        response = self._request(
            "GET",
            f"/proxies/{quote(name, safe='')}/delay",
            params={"url": test_url, "timeout": timeout_ms},
        )
        return response.json()
