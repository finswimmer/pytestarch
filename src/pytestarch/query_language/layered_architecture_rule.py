from __future__ import annotations

from functools import partial
from typing import List, Tuple, Type, Union

from pytestarch import EvaluableArchitecture, Rule
from pytestarch.eval_structure.evaluable_architecture import LayerMapping, ModuleFilter
from pytestarch.query_language.base_language import (
    AccessSpecification,
    BaseLayeredArchitecture,
    LayerBase,
    LayerBehaviorSpecification,
    LayerDefinition,
    LayerName,
    LayerRuleBase,
    LayerRuleObject,
    LayerRuleSubject,
    LayerSpecification,
    RuleApplier,
)
from pytestarch.query_language.exceptions import ImproperlyConfigured
from pytestarch.rule_assessment.rule_check.rule_matcher import (
    LayerRuleMatcher,
    RuleMatcher,
)


class LayeredArchitecture(BaseLayeredArchitecture, LayerName, LayerDefinition):
    """Can be used to define layers within an architecture that are each comprised of modules.
    Note that if a module X is specified as belonging to layer L, all of its submodules are assumed to be part of
    layer L as well."""

    def __init__(self) -> None:
        self._modules_by_layer_name = {}

    @property
    def layer_mapping(self) -> LayerMapping:
        return LayerMapping(self._modules_by_layer_name)

    def layer(self, name: str) -> LayerDefinition:
        underspecified_layers = self._get_layers_without_modules()

        if underspecified_layers:
            raise ImproperlyConfigured(
                f'Specify the modules of layer(s) {", ".join(underspecified_layers)} first.'
            )

        if name in self._modules_by_layer_name:
            raise ImproperlyConfigured(f"Layer {name} already exists.")

        self._modules_by_layer_name[name] = []

        return self

    def _get_layers_without_modules(self) -> List[str]:
        underspecified_layers = [
            layer
            for layer, modules in self._modules_by_layer_name.items()
            if modules == []
        ]
        return underspecified_layers

    def containing_modules(
        self, modules: Union[str, List[str]]
    ) -> Union[LayerName, LayeredArchitecture]:
        layers_without_modules = self._get_layers_without_modules()
        if not layers_without_modules or len(layers_without_modules) > 1:
            raise ImproperlyConfigured(
                "Specify layer name before specifying its modules."
            )

        modules_list = modules if isinstance(modules, list) else [modules]

        module_set = set(modules)
        existing_modules = set(
            [
                value.name
                for values in self._modules_by_layer_name.values()
                for value in values
            ]
        )

        duplicates = module_set.intersection(existing_modules)

        if duplicates:
            raise ImproperlyConfigured(
                f'Module(s) {", ".join(duplicates)} already assigned to a layer.'
            )

        self._modules_by_layer_name[
            layers_without_modules[0]
        ] = self._to_module_objects(modules_list)

        return self

    def have_modules_with_names_matching(
        self,
        regex: str,
    ) -> Union[LayerName, BaseLayeredArchitecture]:
        layers_without_modules = self._get_layers_without_modules()
        if not layers_without_modules or len(layers_without_modules) > 1:
            raise ImproperlyConfigured(
                "Specify layer name before specifying its modules."
            )

        self._modules_by_layer_name[
            layers_without_modules[0]
        ] = self._from_regex_to_module_objects(regex)

        return self

    def __str__(self) -> str:
        layers = [
            f"Layer {layer}: [{', '.join(map(lambda m: m.name, modules))}]"
            for layer, modules in self._modules_by_layer_name.items()
        ]
        return f'Layered Architecture: {"; ".join(layers)}'

    def __getitem__(self, layer: str) -> List[ModuleFilter]:
        return self._modules_by_layer_name[layer]

    def _to_module_objects(self, modules: List[str]) -> List[ModuleFilter]:
        return [ModuleFilter(name=module) for module in modules]

    def _from_regex_to_module_objects(self, regex: str) -> List[ModuleFilter]:
        return [ModuleFilter(name=regex, regex=True)]


class LayerRule(
    RuleApplier,
    LayerRuleBase,
    LayerRuleSubject,
    LayerRuleObject,
    AccessSpecification,
    LayerBehaviorSpecification,
    LayerSpecification,
    LayerBase,
):
    """Represents an architectural rule of the form
    Layer X [verb, such as 'should'] [access type, such as 'be accessed by'] Layer Y
    The modules that each layer contains are to be specified via a LayeredArchitecture object.
    """

    def __init__(
        self, rule_matcher_class: Type[RuleMatcher] = LayerRuleMatcher
    ) -> None:
        self._rule = None
        self._architecture = None
        self._rule_matcher_class = rule_matcher_class

    def based_on(self, architecture: BaseLayeredArchitecture) -> LayerBase:
        if self._architecture is not None:
            raise ImproperlyConfigured("Layered architecture already specified.")

        self._architecture = architecture
        return self

    def layers_that(self) -> LayerRuleSubject:
        if self._architecture is None:
            raise ImproperlyConfigured(
                "Specify a LayeredArchitecture before defining layer behavior."
            )

        self._rule = Rule(rule_matcher_class=partial(self._rule_matcher_class, layer_mapping=self._architecture.layer_mapping)).modules_that()  # type: ignore

        return self

    def are_named(self, layers: Union[str, List[str]]) -> LayerBehaviorSpecification:
        if not self._rule.rule_subjects and isinstance(layers, list):
            raise ImproperlyConfigured(
                "Layer rule subjects cannot be specified in batch."
            )

        layers = self._listify(layers)
        modules = self._get_all_modules_in_layers(layers)

        self._rule = self._rule._add_modules(modules)
        return self

    def should(self) -> LayerBehaviorSpecification:
        self._rule = self._rule.should()
        return self

    def should_only(self) -> LayerBehaviorSpecification:
        self._rule = self._rule.should_only()
        return self

    def should_not(self) -> LayerBehaviorSpecification:
        self._rule = self._rule.should_not()
        return self

    def access_layers_that(self) -> LayerRuleObject:
        self._rule = self._rule.import_modules_that()
        return self

    def be_accessed_by_layers_that(self) -> LayerRuleObject:
        self._rule = self._rule.be_imported_by_modules_that()
        return self

    def access_layers_except_layers_that(self) -> LayerRuleObject:
        self._rule = self._rule.import_modules_except_modules_that()
        return self

    def be_accessed_by_layers_except_layers_that(self) -> LayerRuleObject:
        self._rule = self._rule.be_imported_by_modules_except_modules_that()
        return self

    def access_any_layer(self) -> RuleApplier:
        self._rule = self._rule.import_anything()
        return self

    def be_accessed_by_any_layer(self) -> RuleApplier:
        self._rule = self._rule.be_imported_by_anything()
        return self

    def assert_applies(self, evaluable: EvaluableArchitecture) -> None:
        self._rule.assert_applies(evaluable)

    @classmethod
    def _listify(cls, layers: Union[str, List[str]]) -> List[str]:
        return layers if isinstance(layers, List) else [layers]

    def _get_all_modules_in_layers(self, layers: List[str]) -> List[Tuple[str, bool]]:
        return [
            (module.name, module.regex)
            for layer in layers
            for module in self._architecture[layer]
        ]
