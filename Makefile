# Shared build steps for all three variants.
#
#   make study     generate <stem>.deck.html + <stem>.study.md next to every
#                  slides file in content/ (build artefacts, git-ignored)
#   make quarto    build the Quarto variant into quarto/_site
#   make hugo      build the Hugo variant into hugo/public (+ Pagefind index)
#   make verify-<variant>   browser checks (run in `nix develop .#verify`)
#   make content   re-import content/ from upstream (REF=<commit|branch>)
#   make clean     remove generated decks, study views and variant outputs

PYTHON ?= python3
PAGEFIND ?= npx --yes pagefind@1.3.0
REF    ?= main

# Every Markdown file whose frontmatter says `type: slides`. Generated study
# views carry `type: study`, so they never match.
SLIDES := $(shell grep -l -E '^type:[[:space:]]*slides[[:space:]]*$$' content/modules/*/*.md 2>/dev/null)

.PHONY: study content clean quarto hugo verify-quarto verify-hugo

study:
	$(PYTHON) tools/build_study.py $(SLIDES)

content:
	tools/import_content.sh $(REF)

quarto:
	cd quarto && quarto render

hugo: study
	cd hugo && hugo --gc --cleanDestinationDir
	$(PAGEFIND) --site hugo/public

verify-quarto:
	$(PYTHON) tools/verify_site.py quarto --site quarto/_site

verify-hugo:
	$(PYTHON) tools/verify_site.py hugo --site hugo/public

clean:
	find content -name '*.deck.html' -delete -o -name '*.study.md' -delete
	rm -rf quarto/_site quarto/.quarto quarto/main quarto/modules quarto/hub \
	       quarto/_shared quarto/index.qmd quarto/_generated.yml \
	       hugo/public hugo/resources/_gen hugo/.hugo_build.lock
