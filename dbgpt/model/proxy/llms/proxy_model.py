from dbgpt.model.parameter import ProxyModelParameters


class ProxyModel:
    def __init__(self, model_params: ProxyModelParameters) -> None:
        self._model_params = model_params

    def get_params(self) -> ProxyModelParameters:
        return self._model_params
