.PHONY: help extract extract-pytorch-source extract-graph-break-site extract-derived \
	snapshot-graph-break-site verify clean-output

PY := python3
WEB_PROXY := http://localhost:7824

help:
	@echo "Targets:"
	@echo "  extract                       Run all extractors (source-of-truth → JSON)"
	@echo "  extract-pytorch-source        Run PyTorch source extractors only"
	@echo "  extract-graph-break-site      Run graph-break catalog extractor only"
	@echo "  extract-derived               Run derived views over extractor outputs"
	@echo "  snapshot-graph-break-site     Re-fetch + snapshot the catalog index page"
	@echo "  verify                        Re-run all extractors, ensure byte-identical output"
	@echo "  clean-output                  Remove all generated extractor output JSON"

extract: extract-pytorch-source extract-graph-break-site extract-derived

extract-pytorch-source:
	$(PY) -m extractors.pytorch_source.exc_classes
	$(PY) -m extractors.pytorch_source.config_docstrings
	$(PY) -m extractors.pytorch_source.unsupported_calls

extract-graph-break-site:
	$(PY) -m extractors.graph_break_site.catalog_index

extract-derived:
	$(PY) -m extractors.derived.catalog_source_asymmetry

snapshot-graph-break-site:
	@echo "Fetching catalog index via web-proxy at $(WEB_PROXY)..."
	@curl -sS --max-time 30 $(WEB_PROXY)/fetch \
		-d '{"url":"https://meta-pytorch.org/compile-graph-break-site/","max_size":200000}' \
		| $(PY) -c "import json,sys,hashlib,pathlib; \
r=json.load(sys.stdin); \
assert r.get('ok'), r; \
b=r['content'].encode('utf-8'); \
sha=hashlib.sha256(b).hexdigest()[:12]; \
out=pathlib.Path('extractors/graph_break_site/snapshots/index_'+sha+'.html'); \
out.parent.mkdir(parents=True, exist_ok=True); \
out.write_bytes(b); \
print('snapshot:', out, 'bytes:', len(b), 'sha12:', sha)"

verify: extract
	@echo "Re-running extractors and comparing output hashes..."
	@for f in $$(find extractors -name 'output' -type d -exec find {} -name '*.json' \;); do \
		h1=$$(sha256sum "$$f" | awk '{print $$1}'); \
		echo "$$h1  $$f" >> /tmp/pt2-ontology-verify.txt; \
	done
	@$(MAKE) -s extract >/dev/null
	@for f in $$(find extractors -name 'output' -type d -exec find {} -name '*.json' \;); do \
		h2=$$(sha256sum "$$f" | awk '{print $$1}'); \
		h1=$$(grep " $$f$$" /tmp/pt2-ontology-verify.txt | awk '{print $$1}'); \
		if [ "$$h1" != "$$h2" ]; then \
			echo "DRIFT: $$f changed between runs ($$h1 -> $$h2)"; exit 1; \
		fi; \
	done
	@rm -f /tmp/pt2-ontology-verify.txt
	@echo "OK: all extractor outputs are byte-identical across reruns."

clean-output:
	rm -rf extractors/*/output/
