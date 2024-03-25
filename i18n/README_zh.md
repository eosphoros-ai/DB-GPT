# 国际化提交指南

为确保我们的项目在全球范围内保持高可用性和易于维护，每位开发者在提交代码之前都需要遵循以下国际化（i18n）
处理步骤。这不仅有助于保持我们代码库的国际化最新，也确保了所有用户不论使用何种语言都能获得一致的体验。

## 安装

开始之前，确保已经安装了必要的工具：
- make
- gettext

下面是安装`gettext`的一些方法：

### 对于Debian/Ubuntu及其衍生系统

打开终端，然后运行以下命令来安装gettext：

```bash
sudo apt update
sudo apt install gettext
```

### 对于Fedora、CentOS/RHEL

如果你使用的是Fedora、CentOS或RHEL系统，可以使用下面的命令安装gettext：

- 对于Fedora：
  ```bash
  sudo dnf install gettext
  ```

- 对于CentOS/RHEL：
  ```bash
  # CentOS/RHEL 7 和一些旧版本
  sudo yum install gettext
  # CentOS/RHEL 8 及更高版本
  sudo dnf install gettext
  ```

### 对于Arch Linux

在Arch Linux及其衍生系统上，使用pacman包管理器安装gettext：

```bash
sudo pacman -Sy gettext
```

### 对于MacOS

如果你使用的是MacOS，可以通过Homebrew来安装gettext：

```bash
brew install gettext
```

### 安装完成后

安装完成后，你可以通过在终端运行`xgettext --version`来检查`xgettext`是否成功安装。

如果你依然遇到问题，可能需要检查你的PATH环境变量设置，确保gettext的安装目录已被添加到PATH中，或者尝试重新打开一个新的终端会话。

## 在提交前

请按照以下步骤更新和验证项目的国际化文件：

### 1. 更新 POT 文件

首先，确保 POT 文件包含了最新的可翻译字符串。

```bash
make pot
```

这将扫描源代码中的所有可翻译字符串，并更新 `locales/messages.pot` 文件。

### 2. 更新 PO 文件

然后，更新所有语言的 PO 文件，以包含任何新的或变更的字符串。

```bash
make po
```

如果有新增的可翻译字符串，该命令将自动将它们添加到 PO 文件中。

### 3. 翻译

请确保所有新增的字符串都已翻译。使用您偏好的 PO 文件编辑器（如 Poedit 或 Virtaal）进行翻译。

### 4. 编译 MO 文件

完成翻译后，编译 PO 文件以生成最新的 MO 文件。

```bash
make mo
```

这一步是必要的，因为我们决定将 MO 文件提交到 GitHub。

### 5. 测试

在提交前，请在应用中测试这些翻译以确保它们按预期工作，并且没有破坏任何功能。

### 6. 提交更改

在确保所有翻译都正确无误之后，将 POT、PO 和 MO 文件的更改提交到您的 Git 仓库。

```bash
git add locales/
git commit -m "Update translations"
```

## 注意事项

- 请勿忽略 MO 文件的提交，它们对于确保所有用户都能即时看到最新翻译至关重要。
- 如果您对国际化流程有任何疑问，或需要帮助进行翻译，请及时与项目维护者联系。

通过遵循这些步骤，我们可以保持项目的高度国际化，为全球用户提供无缝的体验。谢谢您的合作和贡献！


## 翻译工具

下述命令可以自动翻译.
```bash
python ./translate_util.py --lang zh_CN --modules app,core,model,rag,serve,storage,util
```

会根据语言、模块自动生成翻译文件，文件在 `locales/zh_CN/LC_MESSAGES/dbgpt_{module}_ai_translated.po`。

对自动生成的翻译文件进行校对，确保翻译质量，然后复制到对应模块中 po 文件中。

现在支持的语言：
- zh_CN
- fr
- ko
- ru