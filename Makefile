# Shared build steps for all three variants.
#
#   make study     generate <stem>.deck.html + <stem>.study.md next to every
#                  slides file in content/ (build artefacts, git-ignored)
#   make content   re-import content/ from upstream (REF=<commit|branch>)
#   make clean     remove generated decks and study views

PYTHON ?= python3
REF    ?= main

# Every Markdown file whose frontmatter says `type: slides`. Generated study
# views carry `type: study`, so they never match.
SLIDES := $(shell grep -l -E '^type:[[:space:]]*slides[[:space:]]*$$' content/modules/*/*.md 2>/dev/null)

.PHONY: study content clean

study:
	$(PYTHON) tools/build_study.py $(SLIDES)

content:
	tools/import_content.sh $(REF)

clean:
	find content -name '*.deck.html' -delete -o -name '*.study.md' -delete
