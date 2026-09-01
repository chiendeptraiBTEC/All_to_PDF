#!/usr/bin/env sh
set -eu

BABELDOC_COMMIT="38d3896dcde9b5a940c62cf5563cadea673a64d3"
PDF2ZH_COMMIT="f8dffcf4c3a33b254391d43514439b975ce8d966"

python -m pip install \
  "BabelDOC @ git+https://github.com/funstory-ai/BabelDOC.git@${BABELDOC_COMMIT}"

# The selected PDFMathTranslate-next commit declares an old PyMuPDF constraint that
# conflicts with BabelDOC 0.6.4. We import only its translator contract and install it
# without dependency resolution; BabelDOC remains the source of truth for PDF deps.
#
# PDFMathTranslate-next imports tomlkit from config/main.py but does not declare it in
# pyproject.toml at this commit. Keep this explicit until the upstream pin changes.
python -m pip install "tomlkit>=0.13,<1"
python -m pip install --no-deps \
  "pdf2zh-next @ git+https://github.com/PDFMathTranslate-next/PDFMathTranslate-next.git@${PDF2ZH_COMMIT}"

python - <<'PY'
from importlib.metadata import version

import babeldoc
from pdf2zh_next.translator.base_translator import BaseTranslator

assert BaseTranslator.__name__ == "BaseTranslator"
print("BabelDOC:", version("BabelDOC"), getattr(babeldoc, "__version__", "installed"))
print("pdf2zh-next:", version("pdf2zh-next"), "translator contract imported")
PY
