from dataclasses import dataclass


@dataclass
class ModelListResponse:
    models: list


@dataclass
class ModelGroupedResponse:
    grouped_models: dict
