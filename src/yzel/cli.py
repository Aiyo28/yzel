"""Yzel CLI — configure connections and manage MCP servers."""

from __future__ import annotations

import click

from yzel import __version__


@click.group()
@click.version_option(version=__version__, prog_name="yzel")
def main() -> None:
    """Узел — Unified MCP connectors for CIS business tools."""


@main.group()
def config() -> None:
    """Управление подключениями / Manage connections."""


@config.command("add-1c")
@click.option("--name", prompt="Имя подключения", help="Connection name")
@click.option("--host", prompt="URL OData (https://server/base/odata/standard.odata)", help="OData endpoint URL")
@click.option("--username", prompt="Имя пользователя", help="1C username")
@click.option("--password", prompt=True, hide_input=True, help="1C password")
@click.option("--fresh", is_flag=True, default=False, help="1C:Fresh cloud deployment")
def add_1c(name: str, host: str, username: str, password: str, fresh: bool) -> None:
    """Добавить подключение к 1С / Add 1C connection."""
    import uuid

    from yzel.core.types import OneCCredential
    from yzel.core.vault import CredentialVault

    vault = CredentialVault()
    cred = OneCCredential(
        name=name,
        host=host,
        username=username,
        password=password,
        is_fresh=fresh,
    )
    connection_id = str(uuid.uuid4())[:8]
    vault.store(connection_id, cred)
    click.echo(f"✓ Подключение '{name}' сохранено (ID: {connection_id})")


@config.command("add-bitrix")
@click.option("--name", prompt="Имя подключения", help="Connection name")
@click.option("--webhook-url", prompt="Webhook URL", help="Bitrix24 webhook URL")
def add_bitrix(name: str, webhook_url: str) -> None:
    """Добавить подключение к Bitrix24 / Add Bitrix24 connection."""
    import uuid

    from yzel.core.types import Bitrix24Credential
    from yzel.core.vault import CredentialVault

    vault = CredentialVault()
    cred = Bitrix24Credential(name=name, webhook_url=webhook_url)
    connection_id = str(uuid.uuid4())[:8]
    vault.store(connection_id, cred)
    click.echo(f"✓ Подключение '{name}' сохранено (ID: {connection_id})")


@config.command("add-moysklad")
@click.option("--name", prompt="Имя подключения", help="Connection name")
@click.option("--token", prompt="Bearer Token", hide_input=True, help="Moysklad API token")
def add_moysklad(name: str, token: str) -> None:
    """Добавить подключение к МойСклад / Add Moysklad connection."""
    import uuid

    from yzel.core.types import MoyskladCredential
    from yzel.core.vault import CredentialVault

    vault = CredentialVault()
    cred = MoyskladCredential(name=name, bearer_token=token)
    connection_id = str(uuid.uuid4())[:8]
    vault.store(connection_id, cred)
    click.echo(f"✓ Подключение '{name}' сохранено (ID: {connection_id})")


@config.command("add-amocrm")
@click.option("--name", prompt="Имя подключения", help="Connection name")
@click.option("--subdomain", prompt="Поддомен AmoCRM (mycompany)", help="AmoCRM subdomain")
@click.option("--client-id", prompt="Client ID", help="OAuth2 client ID")
@click.option("--client-secret", prompt="Client Secret", hide_input=True, help="OAuth2 client secret")
@click.option("--redirect-uri", prompt="Redirect URI", help="OAuth2 redirect URI")
@click.option("--access-token", prompt="Access Token", hide_input=True, help="OAuth2 access token")
@click.option("--refresh-token", prompt="Refresh Token", hide_input=True, help="OAuth2 refresh token")
@click.option("--expires-at", prompt="Expires at (unix timestamp)", type=float, help="Access token expiry")
def add_amocrm(
    name: str,
    subdomain: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    access_token: str,
    refresh_token: str,
    expires_at: float,
) -> None:
    """Добавить подключение к AmoCRM / Add AmoCRM connection."""
    import time
    import uuid

    from yzel.core.types import AmoCRMCredential
    from yzel.core.vault import CredentialVault

    vault = CredentialVault()
    cred = AmoCRMCredential(
        name=name,
        subdomain=subdomain,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        refresh_token_updated_at=time.time(),
    )
    connection_id = str(uuid.uuid4())[:8]
    vault.store(connection_id, cred)
    click.echo(f"✓ Подключение '{name}' сохранено (ID: {connection_id})")


@config.command("add-wildberries")
@click.option("--name", prompt="Имя подключения", help="Connection name")
@click.option("--api-key", prompt="API Key (JWT)", hide_input=True, help="WB seller cabinet JWT token")
@click.option("--sandbox", is_flag=True, default=False, help="Use WB sandbox hosts")
def add_wildberries(name: str, api_key: str, sandbox: bool) -> None:
    """Добавить подключение к Wildberries / Add Wildberries connection."""
    import uuid

    from yzel.core.types import WildberriesCredential
    from yzel.core.vault import CredentialVault

    vault = CredentialVault()
    cred = WildberriesCredential(name=name, api_key=api_key, is_sandbox=sandbox)
    connection_id = str(uuid.uuid4())[:8]
    vault.store(connection_id, cred)
    click.echo(f"✓ Подключение '{name}' сохранено (ID: {connection_id})")


@config.command("add-ozon")
@click.option("--name", prompt="Имя подключения", help="Connection name")
@click.option("--client-id", prompt="Client ID (seller ID)", help="Numeric seller ID")
@click.option("--api-key", prompt="API Key", hide_input=True, help="Ozon API key")
@click.option("--sandbox", is_flag=True, default=False, help="Use Ozon sandbox host")
def add_ozon(name: str, client_id: str, api_key: str, sandbox: bool) -> None:
    """Добавить подключение к Ozon / Add Ozon connection."""
    import uuid

    from yzel.core.types import OzonCredential
    from yzel.core.vault import CredentialVault

    vault = CredentialVault()
    base_url = "https://api-seller-sandbox.ozon.ru" if sandbox else "https://api-seller.ozon.ru"
    cred = OzonCredential(name=name, client_id=client_id, api_key=api_key, base_url=base_url)
    connection_id = str(uuid.uuid4())[:8]
    vault.store(connection_id, cred)
    click.echo(f"✓ Подключение '{name}' сохранено (ID: {connection_id})")


@config.command("add-telegram")
@click.option("--name", prompt="Имя подключения", help="Connection name")
@click.option("--bot-token", prompt="Bot Token (@BotFather)", hide_input=True, help="Token from @BotFather")
def add_telegram(name: str, bot_token: str) -> None:
    """Добавить подключение к Telegram Bot / Add Telegram bot connection."""
    import uuid

    from yzel.core.types import TelegramCredential
    from yzel.core.vault import CredentialVault

    vault = CredentialVault()
    cred = TelegramCredential(name=name, bot_token=bot_token)
    connection_id = str(uuid.uuid4())[:8]
    vault.store(connection_id, cred)
    click.echo(f"✓ Подключение '{name}' сохранено (ID: {connection_id})")


@config.command("add-iiko")
@click.option("--name", prompt="Имя подключения", help="Connection name")
@click.option("--api-login", prompt="apiLogin", hide_input=True, help="apiLogin from iikoWeb (Настройки → API)")
def add_iiko(name: str, api_login: str) -> None:
    """Добавить подключение к iiko / Add iiko Cloud connection."""
    import uuid

    from yzel.core.types import IikoCredential
    from yzel.core.vault import CredentialVault

    vault = CredentialVault()
    cred = IikoCredential(name=name, api_login=api_login)
    connection_id = str(uuid.uuid4())[:8]
    vault.store(connection_id, cred)
    click.echo(f"✓ Подключение '{name}' сохранено (ID: {connection_id})")


@config.command("list")
def list_connections() -> None:
    """Показать все подключения / List all connections."""
    from yzel.core.vault import CredentialVault

    vault = CredentialVault()
    connections = vault.list_connections()

    if not connections:
        click.echo("Нет настроенных подключений. Используйте 'yzel config add-1c'")
        return

    click.echo(f"{'ID':<10} {'Сервис':<12} {'Имя':<20} {'Обновлено'}")
    click.echo("-" * 60)
    for conn in connections:
        click.echo(f"{conn['id']:<10} {conn['service']:<12} {conn['name']:<20} {conn['updated_at']}")


@config.command("remove")
@click.argument("connection_id")
def remove_connection(connection_id: str) -> None:
    """Удалить подключение / Remove a connection."""
    from yzel.core.vault import CredentialVault

    vault = CredentialVault()
    if vault.delete(connection_id):
        click.echo(f"✓ Подключение {connection_id} удалено")
    else:
        click.echo(f"✗ Подключение {connection_id} не найдено")


if __name__ == "__main__":
    main()
