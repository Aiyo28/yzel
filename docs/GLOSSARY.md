# Glossary

One name per concept. Use these terms in code, docs and issues.

| Term | Definition | Aliases to avoid | Owning entity |
|---|---|---|---|
| connector | One supported service (1C, Bitrix24, …) and its MCP server | integration, plugin | `yzel.connectors.<name>` |
| tool kind | One of `read`, `create`, `update`, `delete`; declared once per tool | category, type, mode | tool registry |
| read tool | Kind `read`: changes nothing in the client's system | safe tool, query tool | tool registry |
| create tool | Kind `create`: adds a record or sends a message; repeating it adds another | insert, post | tool registry |
| update tool | Kind `update`: overwrites values; repeating it with the same input changes nothing more | patch, set | tool registry |
| delete tool | Kind `delete`: removes or marks for deletion; repeating it changes nothing more | remove | tool registry |
| write tool | Any tool whose kind is not `read` | mutating tool, action | tool registry |
| read-only mode | Server state where only read tools are listed and callable (`YZEL_READ_ONLY=1`) | safe mode, dry run | tool registry |
| write outcome | The single result class of one write call: `applied`, `rejected`, `not_sent`, `may_have_applied`, `duplicate_refused`, `refused` | status, result | write runner |
| duplicate guard | In-process refusal of an identical create call within 10 minutes unless `again: true` | dedupe, idempotency key | write runner |
| check tool | The read tool a `may_have_applied` message suggests for looking; a hint, not a guard | verify tool | connector server |
