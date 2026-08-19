import base64

import httpx

from app.config import get_settings


class PrintifyError(RuntimeError):
    """Raised when Printify returns a non-2xx response. Carries the response
    body so callers (and the /products error field) can show the real reason
    instead of a bare status code."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Printify API error {status_code}: {body}")


class PrintifyClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.printify_api_token:
            raise RuntimeError("PRINTIFY_API_TOKEN is not set")
        self.shop_id = settings.printify_shop_id
        self._client = httpx.Client(
            base_url=settings.printify_api_base,
            headers={
                "Authorization": f"Bearer {settings.printify_api_token}",
                "Content-Type": "application/json",
                "User-Agent": "adhd-designs/1.0",
            },
            timeout=30.0,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        response = self._client.request(method, path, **kwargs)
        if response.is_error:
            raise PrintifyError(response.status_code, response.text)
        if not response.content:
            return {}
        return response.json()

    def list_blueprints(self) -> list[dict]:
        return self._request("GET", "/catalog/blueprints.json")

    def get_blueprint(self, blueprint_id: int) -> dict:
        return self._request("GET", f"/catalog/blueprints/{blueprint_id}.json")

    def list_print_providers(self, blueprint_id: int) -> list[dict]:
        return self._request("GET", f"/catalog/blueprints/{blueprint_id}/print_providers.json")

    def get_variants(self, blueprint_id: int, print_provider_id: int) -> dict:
        return self._request(
            "GET",
            f"/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json",
        )

    def upload_image(self, file_name: str, content: bytes) -> dict:
        payload = {"file_name": file_name, "contents": base64.b64encode(content).decode("ascii")}
        return self._request("POST", "/uploads/images.json", json=payload)

    def list_shops(self) -> list[dict]:
        return self._request("GET", "/shops.json")

    def create_product(self, payload: dict, shop_id: str | None = None) -> dict:
        shop = shop_id or self.shop_id
        if not shop:
            raise RuntimeError("PRINTIFY_SHOP_ID is not set and no shop_id was provided")
        return self._request("POST", f"/shops/{shop}/products.json", json=payload)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PrintifyClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
