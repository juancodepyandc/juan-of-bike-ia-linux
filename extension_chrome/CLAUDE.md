# Aurora-Connect Chrome extension — owned by `cowork-connector-keeper`

When editing files in this directory, `cowork-connector-keeper` rules apply.

## Hard rules

- **Manifest v3**. Service workers, not background pages. No MV2 APIs.
- The handshake message format with `auroraExtensionBridge.ts` (in `application/src/services/`) is fixed — extension and bridge agree on it. Don't break either side.
- DOM selectors in content scripts are fragile — when adding/updating, verify against a current page render.
- Permissions in `manifest.json` are scoped to known hosts. Don't add `<all_urls>` without justification.

See `.claude/agents/cowork-lead.md` and `.claude/agents/cowork-connector-keeper.md` for the full lead spec.
