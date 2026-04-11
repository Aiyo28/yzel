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
