from dbgpt_serve.core.config import GPTsAppCommonConfig


def scan_app_configs():
    """Scan and register all app configs."""
    from dbgpt.util.module_utils import ModelScanner, ScannerConfig

    modules = ["dbgpt_app.scene"]

    scanner = ModelScanner[GPTsAppCommonConfig]()
    for module in modules:
        config = ScannerConfig(
            module_path=module,
            base_class=GPTsAppCommonConfig,
            recursive=True,
            specific_files=["config"],
        )
        scanner.scan_and_register(config)
    return scanner.get_registered_items()
