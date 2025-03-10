# Globalization (i18n) workflow Makefile

# Define variables
LOCALEDIR = ./locales
PACKAGES_DIR = ../packages

# Define packages and their mapping
# format: package-name:src-name:domain
PACKAGES = dbgpt-core:dbgpt:dbgpt dbgpt-app:dbgpt_app:dbgpt_app dbgpt-client:dbgpt_client:dbgpt_client \
          dbgpt-ext:dbgpt_ext:dbgpt_ext dbgpt-serve:dbgpt_serve:dbgpt_serve \
          dbgpt-accelerator:dbgpt_accelerator:dbgpt_accelerator

# Define supported languages
LANGUAGES = zh_CN ja ko fr ru
LANGUAGE ?= $(LANGUAGES)

.PHONY: help pot po mo clean

all: pot po mo

# Generate POT files for all packages and modules
pot:
	@echo "Generating POT files for packages..."
	@mkdir -p $(LOCALEDIR)/pot
	@for pkg_info in $(PACKAGES); do \
		pkg_name=$$(echo $$pkg_info | cut -d: -f1); \
		src_name=$$(echo $$pkg_info | cut -d: -f2); \
		domain=$$(echo $$pkg_info | cut -d: -f3); \
		src_dir=$(PACKAGES_DIR)/$$pkg_name/src/$$src_name; \
		echo "Processing $$pkg_name..."; \
		if [ -d "$$src_dir" ]; then \
			for dir_or_file in "$$src_dir"/*; do \
				if [ -d "$$dir_or_file" ]; then \
					module=$$(basename "$$dir_or_file"); \
					if [ "$$module" != "__pycache__" ] && [ "$$module" != "tests" ]; then \
						echo "  Processing directory $$module..."; \
						find "$$dir_or_file" -type f -name "*.py" -exec xgettext --from-code=UTF-8 -o $(LOCALEDIR)/pot/$${domain}_$${module}.pot --language=Python -k_ -n {} + 2>/dev/null || true; \
					fi; \
				elif [ -f "$$dir_or_file" ]; then \
					case "$$dir_or_file" in \
						*.py) \
							module=$$(basename "$$dir_or_file" .py); \
							if [ "$$module" != "__init__" ]; then \
								echo "  Processing file $$module.py..."; \
								xgettext --from-code=UTF-8 -o $(LOCALEDIR)/pot/$${domain}_$${module}.pot --language=Python -k_ -n "$$dir_or_file" 2>/dev/null || true; \
							fi;; \
					esac; \
				fi; \
			done; \
		else \
			echo "  Source directory not found: $$src_dir"; \
		fi; \
	done

# Update or create new .po files
po: pot
	@for lang in $(LANGUAGE); do \
		echo "Processing language: $$lang"; \
		mkdir -p $(LOCALEDIR)/$$lang/LC_MESSAGES; \
		for pot in $(LOCALEDIR)/pot/*.pot; do \
			if [ -f "$$pot" ]; then \
				domain=$$(basename $$pot .pot); \
				if [ -f $(LOCALEDIR)/$$lang/LC_MESSAGES/$$domain.po ]; then \
					echo "Updating $$lang translation for $$domain"; \
					msgmerge --update $(LOCALEDIR)/$$lang/LC_MESSAGES/$$domain.po $$pot; \
				else \
					echo "Creating $$lang translation for $$domain"; \
					msginit --no-translator -l $$lang -o $(LOCALEDIR)/$$lang/LC_MESSAGES/$$domain.po -i $$pot --locale=$$lang.UTF-8; \
				fi; \
			fi; \
		done; \
	done

# Compile .po files to .mo files
mo:
	@for lang in $(LANGUAGE); do \
		echo "Compiling translations for $$lang"; \
		for po in $(LOCALEDIR)/$$lang/LC_MESSAGES/*.po; do \
			if [ -f "$$po" ]; then \
				domain=$$(basename $$po .po); \
				echo "  Compiling $$domain"; \
				msgfmt -o $(LOCALEDIR)/$$lang/LC_MESSAGES/$$domain.mo $$po; \
			fi; \
		done; \
	done
# Fix encoding issues in .po files
fix-encoding:
	@echo "Fixing encoding issues in .po files..."
	@for lang in $(LANGUAGES); do \
		echo "Processing language: $$lang"; \
		for po in $(LOCALEDIR)/$$lang/LC_MESSAGES/*.po; do \
			if [ -f "$$po" ]; then \
				echo "  Fixing $$po..."; \
				# Ensure charset is UTF-8 \
				sed -i 's/charset=.*/charset=UTF-8\\n"/' "$$po"; \
				# Ensure Content-Transfer-Encoding is 8bit \
				sed -i 's/Content-Transfer-Encoding: .*/Content-Transfer-Encoding: 8bit\\n"/' "$$po"; \
			fi; \
		done; \
	done
	@echo "Encoding fixes complete."
# Clean up generated files
clean:
	@find $(LOCALEDIR) -type f -name "*.mo" -delete
	@find $(LOCALEDIR) -type f -name "*.po" -delete
	@rm -rf $(LOCALEDIR)/pot
	@echo "Cleanup complete."

help:
	@echo "Available commands:"
	@echo "  pot  - Generate POT files for each package module."
	@echo "  po   - Update existing .po files or create them if they don't exist."
	@echo "  mo   - Compile .po files into .mo files for use in the application."
	@echo "  fix-encoding - Fix charset and encoding issues in .po files."
	@echo "  clean - Clean up generated files."
	@echo "  help - Show this help message."
	@echo ""
	@echo "Typical workflow for translation:"
	@echo "1. Run 'make pot' to extract all translatable strings into POT files."
	@echo "2. Run 'make po' to update .po files with new translations."
	@echo "3. Translate the strings in .po files using a PO file editor."
	@echo "4. Run 'make mo' to compile the translated .po files into .mo files."
	@echo "5. Run 'make clean' to clean up if necessary."
	@echo ""
	@echo "Use 'LANGUAGE=<lang>' to specify languages."
	@echo "Available languages: $(LANGUAGES)"