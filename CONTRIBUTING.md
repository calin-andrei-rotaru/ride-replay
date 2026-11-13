# Working on Ride Replay

Keep changes focused on repeatable climb comparisons and the private import workflow.

## Commit regularly

Make a commit when a coherent change is complete and its relevant checks pass. Keep unrelated work in separate commits and use a message that describes the resulting behavior. Small documentation changes are useful checkpoints too; avoid collecting several finished tasks into one large commit.

Before committing, review `git diff` and `git diff --cached`. Keep real ride files, private databases, import manifests, cloud state, and credentials out of Git. Store private working data under ignored `data/` or outside the checkout.

## Check the changed behavior

For Python imports, matching, and exports, run `python -m pytest -q` in an activated environment. For dashboard changes, run these commands from `web/`:

```text
npm run build
npm run typecheck
npm run check:public
```

For a deployment, also run `npm run check:deployment -- <production-url>`. That check inspects the public page, snapshot, referenced assets, and private-path responses. It does not replace visual or interaction checks in a browser.

For infrastructure changes, run `terraform -chdir=infra fmt -check` and `terraform -chdir=infra validate` after initialization. Cloud plan/apply needs the intended account and budget; record actual execution status separately from local validation.

Documentation-only changes need link, command, and formatting checks. Add tests for meaningful new behavior or regressions, and keep the synthetic snapshot reproducible.

## Keep evidence accurate

The public demo currently uses synthetic rides. Keep that label visible. Record real-ride checks, Databricks run IDs, deployment evidence, and infrastructure execution in the [verification record](docs/verification.md) only after they happen. The [usage guide](docs/guide.md) documents the data contract and matching assumptions.
