# Internationalization Submission Guide

To ensure our project remains highly usable and maintainable across the globe, 
every developer is required to follow the steps below for internationalization (i18n) 
processing before submitting code. This not only helps keep our codebase's 
internationalization up to date but also ensures a consistent experience for all users, 
regardless of their language.

## Installation

Before you start, make sure you have the necessary tools installed:
- make
- gettext

Here are some ways to install `gettext`:

### Ubuntu/Debian And Derivatives

```bash
sudo apt update
sudo apt install gettext
````

### Fedora/CentOS/RHEL

- Fedora:
    ```bash
    sudo dnf install gettext
    ```
- CentOS/RHEL:
    ```bash
    # CentOS/RHEL 7 And Older
    sudo yum install gettext
    # CentOS/RHEL 8 And Newer
    sudo dnf install gettext
    ```

### Arch Linux

```bash
sudo pacman -Sy gettext
```

### MacOS

```bash
brew install gettext
```

## Before You Submit

Please follow these steps to update and verify the project's internationalization files:

### 1. Update POT File

First, make sure the POT file contains the latest translatable strings.

```bash
make pot
```

This will scan all translatable strings in the source code and update the 
`locales/messages.pot` file.

### 2. Update PO Files

Next, update the PO files for all languages to include any new or changed strings.

```bash
make po
```

If there are new translatable strings, this command will automatically add them to the PO files.

### 3. Translate

Ensure all new strings have been translated. Use your preferred PO file editor 
(like Poedit or Virtaal) for translation.

### 4. Compile MO Files

After translating, compile the PO files to generate the latest MO files.

```bash
make mo
```

This step is crucial because we've decided to include MO files in our GitHub submissions.

### 5. Test

Before submitting, please test these translations in the application to ensure they 
work as expected and do not break any functionality.

### 6. Submit Changes

After verifying that all translations are correct and functional, submit the changes of 
POT, PO, and MO files to your Git repository.

```bash
git add locales/
git commit -m "Update translations"
```

## Considerations

- Do not omit the submission of MO files; they are crucial for ensuring that all users 
can see the latest translations immediately.
- If you have any questions about the internationalization process or need help with 
translations, please contact the project maintainers promptly.

By following these steps, we can maintain a high level of internationalization in our 
project, providing a seamless experience for users worldwide. Thank you for your 
cooperation and contribution!

## Translating Utilities

Running the following commands will automatically generate the latest translations:

```bash
python ./translate_util.py --lang zh_CN --modules app,core,model,rag,serve,storage,util
```

It will generate the latest translations for the specified modules and languages in the 
directories `locales/zh_CN/LC_MESSAGES/dbgpt_{module}_ai_translated.po`.

Check it and make sure it is correct. Then copy it to the `locales/zh_CN/LC_MESSAGES/dbgpt_{module}.po` file.

Now support the following languages:
- zh_CN
- fr
- ko
- ru