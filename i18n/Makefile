# Globalization (i18n) workflow Makefile

# Define variables
DOMAIN = dbgpt
LOCALEDIR = ./locales
SRC_DIR = ../dbgpt
SUBPACKAGES = agent app cli client configs core datasource model rag serve storage train util vis

# Define supported languages
# Default: English (en)
LANGUAGES = zh_CN ja ko fr ru

.PHONY: help pot po mo clean

all: pot po mo

# Generate POT files for each existing subpackage
pot:
	@echo "Generating POT files for subpackages..."
	@$(foreach pkg,$(SUBPACKAGES),\
		if [ -d $(SRC_DIR)/$(pkg) ]; then \
			echo "Processing $(pkg) package..."; \
			mkdir -p $(LOCALEDIR)/pot; \
			find $(SRC_DIR)/$(pkg) -name '*.py' -exec xgettext -o $(LOCALEDIR)/pot/$(DOMAIN)_$(pkg).pot --language=Python -k_ -n {} +; \
		else \
			echo "Skipping $(pkg) as it does not exist."; \
		fi; \
	)

# Update or create new .po files for each language
po: pot
	@for lang in $(LANGUAGES); do \
		for pkg in $(SUBPACKAGES); do \
			if [ -f $(LOCALEDIR)/pot/$(DOMAIN)_$$pkg.pot ]; then \
				mkdir -p $(LOCALEDIR)/$$lang/LC_MESSAGES; \
				if [ -f $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN)_$$pkg.po ]; then \
					echo "Updating $$lang PO file for $$pkg..."; \
					msgmerge --update $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN)_$$pkg.po $(LOCALEDIR)/pot/$(DOMAIN)_$$pkg.pot; \
				else \
					echo "Creating $$lang PO file for $$pkg..."; \
					msginit --no-translator -l $$lang -o $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN)_$$pkg.po -i $(LOCALEDIR)/pot/$(DOMAIN)_$$pkg.pot; \
				fi; \
			else \
				echo "Skipping $$pkg for $$lang as POT file does not exist."; \
			fi; \
		done \
	done


# Compile .po files to .mo files
mo:
	@for lang in $(LANGUAGES); do \
		for pkg in $(SUBPACKAGES); do \
			if [ -f $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN)_$$pkg.po ]; then \
				echo "Compiling $$lang MO file for $$pkg..."; \
				msgfmt -o $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN)_$$pkg.mo $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN)_$$pkg.po; \
			else \
				echo "Skipping $$pkg for $$lang as PO file does not exist."; \
			fi; \
		done \
	done

# Clean up generated files
clean:
	@find $(LOCALEDIR) -type f -name "*.mo" -delete
	@rm -rf $(LOCALEDIR)/pot
	@echo "Cleanup complete."

help:
	@echo "Available commands:"
	@echo "  pot  - Generate POT files for each subpackage."
	@echo "  po   - Update existing .po files or create them if they don't exist, for each subpackage."
	@echo "  mo   - Compile .po files into .mo files for use in the application, for each subpackage."
	@echo "  clean - Clean up generated files."
	@echo "  help - Show this help message."
	@echo ""
	@echo "Typical workflow for translation:"
	@echo "1. Run 'make pot' to extract all translatable strings into POT files."
	@echo "2. Run 'make po' to update .po files with new translations."
	@echo "3. Translate the strings in .po files using a PO file editor."
	@echo "4. Run 'make mo' to compile the translated .po files into .mo files."
	@echo "5. Run 'make clean' to clean up if necessary."
