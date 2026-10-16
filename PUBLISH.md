# Publish status (2026-10-16 Asia/Shanghai)

## Public GitHub marketplace

- Repo: https://github.com/JimCui0508/sgpt-cc-marketplace
- Layout: plugin root = repository root (marketplace.json + plugin.json under `.claude-plugin/`)

```bash
claude plugin marketplace add JimCui0508/sgpt-cc-marketplace
claude plugin install sgpt-cc@sgpt-cc-marketplace
```

## Local (always works)

```bash
claude plugin marketplace add /Users/didi/Projects/goal-mode-policy/plugins
claude plugin install sgpt-cc@goal-mode-policy-plugins
# or:
claude --plugin-dir /Users/didi/Projects/goal-mode-policy/plugins/sgpt-cc
```

## Anthropic directory (claude.ai/directory)

Separate from own marketplace:

1. Public GitHub repository (this repo)
2. Paid claude.ai plan
3. Submit at https://claude.ai/directory/manage + Anthropic review
4. Cannot self-submit into reserved `claude-plugins-official`

## Notes

- Plugin is observability only (SGPT), not a model improver.
- Paper short version stays anonymous; public URL lives here, not forced into double-blind PDF.
