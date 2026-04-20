"""Bitrix24 REST API client.

Webhook-based — no OAuth, no token refresh. Each portal provides a
permanent webhook URL like https://company.bitrix24.ru/rest/1/abc123/.
All methods append the method name + .json to this base.

Rate limit: 2 req/sec (leaky bucket). The server returns HTTP 429 with
no Retry-After header, so we enforce client-side throttling.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx


class RateLimiter:
    """Leaky-bucket rate limiter for Bitrix24's 2 req/sec limit.

    Enforces minimum interval between requests. Async-safe via lock.
    """

    def __init__(self, max_per_second: float = 2.0) -> None:
        self._min_interval = 1.0 / max_per_second
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request = time.monotonic()


class Bitrix24Client:
    """Async client for Bitrix24 REST API via webhook."""

    def __init__(self, webhook_url: str) -> None:
        self._base_url = webhook_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._limiter = RateLimiter(max_per_second=2.0)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def _call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a Bitrix24 REST method with rate limiting.

        Args:
            method: REST method name (e.g., 'crm.lead.list')
            params: Method parameters

        Returns:
            Full response dict with 'result', optionally 'total' and 'next'.

        Raises:
            Bitrix24Error: On any non-2xx response or on a 200-with-error body.
        """
        await self._limiter.acquire()
        url = f"{self._base_url}/{method}.json"
        client = await self._get_client()
        response = await client.post(url, json=params or {})

        # Parse body defensively — Bitrix returns error envelopes at several
        # different HTTP statuses (200 with error field, 400, 401, 403, 404,
        # 429 without Retry-After). All collapse into Bitrix24Error here.
        try:
            data = response.json()
        except ValueError:
            data = {}

        if response.status_code >= 400 or (isinstance(data, dict) and "error" in data):
            code = str((data or {}).get("error") or response.status_code)
            description = (data or {}).get("error_description") or (
                response.text[:200] or response.reason_phrase
            )
            raise Bitrix24Error(
                code=code,
                description=description,
                status_code=response.status_code,
            )
        return data

    # --- CRM: Leads ---

    async def get_leads(
        self,
        select: list[str] | None = None,
        filter_params: dict[str, Any] | None = None,
        order: dict[str, str] | None = None,
        start: int = 0,
    ) -> dict[str, Any]:
        """Получить список лидов / Get leads list."""
        params: dict[str, Any] = {"start": start}
        if select:
            params["select"] = select
        if filter_params:
            params["filter"] = filter_params
        if order:
            params["order"] = order
        return await self._call("crm.lead.list", params)

    async def get_lead(self, lead_id: int) -> dict[str, Any]:
        """Получить лид по ID / Get lead by ID."""
        return await self._call("crm.lead.get", {"ID": lead_id})

    async def create_lead(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Создать лид / Create a lead."""
        return await self._call("crm.lead.add", {"fields": fields})

    async def update_lead(self, lead_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        """Обновить лид / Update a lead."""
        return await self._call("crm.lead.update", {"ID": lead_id, "fields": fields})

    # --- CRM: Contacts ---

    async def get_contacts(
        self,
        select: list[str] | None = None,
        filter_params: dict[str, Any] | None = None,
        order: dict[str, str] | None = None,
        start: int = 0,
    ) -> dict[str, Any]:
        """Получить список контактов / Get contacts list."""
        params: dict[str, Any] = {"start": start}
        if select:
            params["select"] = select
        if filter_params:
            params["filter"] = filter_params
        if order:
            params["order"] = order
        return await self._call("crm.contact.list", params)

    async def get_contact(self, contact_id: int) -> dict[str, Any]:
        """Получить контакт по ID / Get contact by ID."""
        return await self._call("crm.contact.get", {"ID": contact_id})

    async def create_contact(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Создать контакт / Create a contact."""
        return await self._call("crm.contact.add", {"fields": fields})

    async def update_contact(self, contact_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        """Обновить контакт / Update a contact."""
        return await self._call("crm.contact.update", {"ID": contact_id, "fields": fields})

    # --- CRM: Deals ---

    async def get_deals(
        self,
        select: list[str] | None = None,
        filter_params: dict[str, Any] | None = None,
        order: dict[str, str] | None = None,
        start: int = 0,
    ) -> dict[str, Any]:
        """Получить список сделок / Get deals list."""
        params: dict[str, Any] = {"start": start}
        if select:
            params["select"] = select
        if filter_params:
            params["filter"] = filter_params
        if order:
            params["order"] = order
        return await self._call("crm.deal.list", params)

    async def get_deal(self, deal_id: int) -> dict[str, Any]:
        """Получить сделку по ID / Get deal by ID."""
        return await self._call("crm.deal.get", {"ID": deal_id})

    async def create_deal(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Создать сделку / Create a deal."""
        return await self._call("crm.deal.add", {"fields": fields})

    async def update_deal(self, deal_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        """Обновить сделку / Update a deal."""
        return await self._call("crm.deal.update", {"ID": deal_id, "fields": fields})

    # --- CRM: Companies ---

    async def get_companies(
        self,
        select: list[str] | None = None,
        filter_params: dict[str, Any] | None = None,
        order: dict[str, str] | None = None,
        start: int = 0,
    ) -> dict[str, Any]:
        """Получить список компаний / Get companies list."""
        params: dict[str, Any] = {"start": start}
        if select:
            params["select"] = select
        if filter_params:
            params["filter"] = filter_params
        if order:
            params["order"] = order
        return await self._call("crm.company.list", params)

    async def get_company(self, company_id: int) -> dict[str, Any]:
        """Получить компанию по ID / Get company by ID."""
        return await self._call("crm.company.get", {"ID": company_id})

    async def create_company(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Создать компанию / Create a company."""
        return await self._call("crm.company.add", {"fields": fields})

    async def update_company(self, company_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        """Обновить компанию / Update a company."""
        return await self._call("crm.company.update", {"ID": company_id, "fields": fields})

    # --- Tasks ---

    async def get_tasks(
        self,
        select: list[str] | None = None,
        filter_params: dict[str, Any] | None = None,
        order: dict[str, str] | None = None,
        start: int = 0,
    ) -> dict[str, Any]:
        """Получить список задач / Get tasks list."""
        params: dict[str, Any] = {"start": start}
        if select:
            params["select"] = select
        if filter_params:
            params["filter"] = filter_params
        if order:
            params["order"] = order
        return await self._call("tasks.task.list", params)

    async def get_task(self, task_id: int) -> dict[str, Any]:
        """Получить задачу по ID / Get task by ID."""
        return await self._call("tasks.task.get", {"taskId": task_id})

    async def create_task(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Создать задачу / Create a task."""
        return await self._call("tasks.task.add", {"fields": fields})

    async def update_task(self, task_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        """Обновить задачу / Update a task."""
        return await self._call("tasks.task.update", {"taskId": task_id, "fields": fields})

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class Bitrix24Error(Exception):
    """Bitrix24 error — unified across HTTP-level (4xx/5xx) and app-level failures."""

    def __init__(self, code: str, description: str, status_code: int = 200) -> None:
        self.code = code
        self.description = description
        self.status_code = status_code
        super().__init__(f"Bitrix24 error [{status_code}/{code}]: {description}")
