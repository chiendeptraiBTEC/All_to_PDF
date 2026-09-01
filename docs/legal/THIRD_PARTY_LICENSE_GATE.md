# Third-party license gate

**Status:** engineering gate implemented; legal approval remains an organizational decision.

## Pinned engine dependencies

| Dependency | Snapshot | License observed at snapshot |
|---|---|---|
| BabelDOC | `38d3896dcde9b5a940c62cf5563cadea673a64d3` | GNU AGPL v3 |
| PDFMathTranslate-next | `f8dffcf4c3a33b254391d43514439b975ce8d966` | GNU AGPL v3 |

Sources:

- `https://github.com/funstory-ai/BabelDOC/blob/38d3896dcde9b5a940c62cf5563cadea673a64d3/LICENSE`
- `https://github.com/PDFMathTranslate-next/PDFMathTranslate-next/blob/f8dffcf4c3a33b254391d43514439b975ce8d966/LICENSE`

Both license files identify the GNU Affero General Public License, Version 3. This file records
that fact; it is not legal advice and does not decide whether a specific deployment model
satisfies the license.

## Fail-closed engineering control

`build_worker()` refuses to create a production engine worker unless
`ATP_THIRD_PARTY_LICENSE_ACKNOWLEDGED=true`.

The acknowledgement means the deployer has reviewed this gate and made the required
organizational/legal decision. It does **not** waive, replace, or reinterpret AGPL obligations.
The API can run without the acknowledgement because the API image does not install BabelDOC;
the dedicated worker image is the component that installs and executes the pinned engine.

## Release checklist

Before setting the acknowledgement in a production environment:

1. Decide whether the service/source distribution model is compatible with AGPL v3.
2. Preserve upstream copyright/license notices.
3. Document source-availability obligations for any modified/combined network service.
4. Record the decision owner and date in the deployment change record.
5. Re-run this review whenever either pinned engine commit changes.

A release with the production worker and acknowledgement unset is intentionally blocked.
