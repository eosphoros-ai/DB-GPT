"""Prompt template registry.

This module is deprecated. we will remove it in the future.
"""
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import defaultdict
from typing import Dict, List, Optional

_DEFAULT_MODEL_KEY = "___default_prompt_template_model_key__"
_DEFUALT_LANGUAGE_KEY = "___default_prompt_template_language_key__"


class PromptTemplateRegistry:
    """
    The PromptTemplateRegistry class is a manager of prompt template of all scenes.
    """

    def __init__(self) -> None:
        self.registry = defaultdict(dict)  # type: ignore

    def register(
        self,
        prompt_template,
        language: str = "en",
        is_default: bool = False,
        model_names: Optional[List[str]] = None,
        scene_name: Optional[str] = None,
    ) -> None:
        """Register prompt template with scene name, language
        registry dict format:
        {
            "<scene_name>": {
                _DEFAULT_MODEL_KEY: {
                    _DEFUALT_LANGUAGE_KEY: <prompt_template>,
                    "<language>": <prompt_template>
                },
                "<model_name>": {
                    "<language>": <prompt_template>
                }
            }
        }
        """
        if not scene_name:
            scene_name = prompt_template.template_scene
        if not scene_name:
            raise ValueError("Prompt template scene name cannot be empty")
        if not model_names:
            model_names = [_DEFAULT_MODEL_KEY]
        scene_registry = self.registry[scene_name]
        _register_scene_prompt_template(
            scene_registry, prompt_template, language, model_names
        )
        if is_default:
            _register_scene_prompt_template(
                scene_registry,
                prompt_template,
                _DEFUALT_LANGUAGE_KEY,
                [_DEFAULT_MODEL_KEY],
            )
            _register_scene_prompt_template(
                scene_registry, prompt_template, language, [_DEFAULT_MODEL_KEY]
            )

    def get_prompt_template(
        self,
        scene_name: str,
        language: str,
        model_name: str,
        proxyllm_backend: Optional[str] = None,
    ):
        """Get prompt template with scene name, language and model name
        proxyllm_backend: see CFG.PROXYLLM_BACKEND
        """
        scene_registry = self.registry[scene_name]

        print(
            f"Get prompt template of scene_name: {scene_name} with model_name: {model_name}, proxyllm_backend: {proxyllm_backend}, language: {language}"
        )
        registry = None
        if proxyllm_backend:
            registry = scene_registry.get(proxyllm_backend)
        if not registry:
            registry = scene_registry.get(model_name)
        if not registry:
            registry = scene_registry.get(_DEFAULT_MODEL_KEY)
            if not registry:
                raise ValueError(
                    f"There is no template with scene name {scene_name}, model name {model_name}, language {language}"
                )
        else:
            print(
                f"scene: {scene_name} has custom prompt template of model: {model_name}, language: {language}"
            )
        prompt_template = registry.get(language)
        if not prompt_template:
            prompt_template = registry.get(_DEFUALT_LANGUAGE_KEY)
        return prompt_template


def _register_scene_prompt_template(
    scene_registry: Dict[str, Dict],
    prompt_template,
    language: str,
    model_names: List[str],
):
    for model_name in model_names:
        if model_name not in scene_registry:
            scene_registry[model_name] = dict()
        registry = scene_registry[model_name]
        registry[language] = prompt_template
