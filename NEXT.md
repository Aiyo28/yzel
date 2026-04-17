# Next

## Continue
- [ ] Manual testing of all 4 connectors via mock servers (testing-guide.md in vault)
- [ ] Write Habr article draft
- [ ] Test against real 1C instance (VM or partner access)
- [ ] Implement license key system for enterprise features (JWT)
- [ ] Design `WhatsAppConnector` interface — wacli (free) + BSP adapter (paid) behind same contract (see [D] #8a)
- [ ] Wire wacli as sidecar subprocess per tenant, not library import

## Decide
- Windows VM tool: Parallels vs UTM for 1C Training Version testing
- Whether to add HTTP Service mode alongside OData
- Russian payment processing: Юкасса vs Robokassa
- BSP choice for paid-tier WhatsApp: Twilio vs WhatsApp Cloud API direct (defer until first enterprise pilot asks)

## Blocked
- Real 1C integration test blocked until VM or partner access obtained

## Guardrail
- No public "WhatsApp integration" marketing until BSP adapter exists — visibility spike triggers Meta enforcement (see Knowledge/Tech - Tools - wacli WhatsApp CLI.md)

Updated: 2026-04-17
