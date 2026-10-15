# Yzel is a connector layer: real-time, self-hosted, and never modifies the client's 1C

Context: each of these invites a feature request that would change the architecture. We decided Yzel stays real-time MCP queries only (no ETL pipeline, no data warehouse), connectors only (no operational logic on top of a business tool), self-hosted (no hosted service, stdio transport, credentials stay local), and read/write through published OData/HTTP APIs only (no BSL extensions, no changes to a client's 1C configuration).

Consequence: a feature that needs persistence of business data, a server we run, or a change inside the client's 1C does not belong in this repo.
