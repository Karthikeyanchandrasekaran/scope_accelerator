import copy
from typing import Any

import streamlit as st

from components import COMPONENT_TYPES


def initialize_state() -> None:
    defaults = {
        "components": [],
        "component_counter": 1,
        "generated_script": "",
        "job_name": "CustomerUsagePipeline",
        "environment": "DEV",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def add_component(
    component_type: str,
    config: dict[str, Any],
) -> None:
    st.session_state.components.append(
        {
            "id": (
                st.session_state.component_counter
            ),
            "type": component_type,
            "config": copy.deepcopy(config),
        }
    )

    st.session_state.component_counter += 1
    st.session_state.generated_script = ""


def update_component(
    index: int,
    config: dict[str, Any],
) -> None:
    st.session_state.components[index][
        "config"
    ] = copy.deepcopy(config)

    st.session_state.generated_script = ""


def delete_component(
    index: int,
) -> None:
    st.session_state.components.pop(index)
    st.session_state.generated_script = ""


def move_component(
    index: int,
    direction: int,
) -> None:
    target_index = index + direction

    components = st.session_state.components

    if 0 <= target_index < len(components):
        components[index], components[target_index] = (
            components[target_index],
            components[index],
        )

        st.session_state.generated_script = ""


def get_available_datasets() -> list[str]:
    datasets: list[str] = []

    output_fields = {
        "Read File": "dataset_name",
        "Select Columns": "output_dataset",
        "Filter": "output_dataset",
        "Join": "output_dataset",
        "Aggregate": "output_dataset",
        "Union": "output_dataset",
    }

    for component in st.session_state.components:
        field = output_fields.get(
            component["type"]
        )

        if not field:
            continue

        dataset = component["config"].get(
            field
        )

        if dataset and dataset not in datasets:
            datasets.append(dataset)

    return datasets


def export_workflow() -> dict[str, Any]:
    return {
        "job_name": st.session_state.job_name,
        "environment": (
            st.session_state.environment
        ),
        "components": copy.deepcopy(
            st.session_state.components
        ),
    }


def load_workflow(
    workflow_data: dict[str, Any],
) -> tuple[bool, str]:
    if not isinstance(workflow_data, dict):
        return False, "Workflow must be a JSON object."

    components = workflow_data.get(
        "components"
    )

    if not isinstance(components, list):
        return False, "Workflow must contain components."

    for index, component in enumerate(
        components,
        start=1,
    ):
        if not isinstance(component, dict):
            return (
                False,
                f"Component {index} is invalid.",
            )

        if component.get("type") not in COMPONENT_TYPES:
            return (
                False,
                f"Unsupported component type at "
                f"position {index}.",
            )

        if not isinstance(
            component.get("config"),
            dict,
        ):
            return (
                False,
                f"Component {index} has no config.",
            )

    restored = []
    highest_id = 0

    for index, component in enumerate(
        components,
        start=1,
    ):
        component_id = component.get(
            "id",
            index,
        )

        try:
            component_id = int(component_id)
        except (TypeError, ValueError):
            component_id = index

        highest_id = max(
            highest_id,
            component_id,
        )

        restored.append(
            {
                "id": component_id,
                "type": component["type"],
                "config": copy.deepcopy(
                    component["config"]
                ),
            }
        )

    environment = workflow_data.get(
        "environment",
        "DEV",
    )

    if environment not in {
        "DEV",
        "TEST",
        "PROD",
    }:
        environment = "DEV"

    st.session_state.components = restored
    st.session_state.component_counter = (
        highest_id + 1
    )

    st.session_state.job_name = str(
        workflow_data.get(
            "job_name",
            "RestoredWorkflow",
        )
    )

    st.session_state.environment = environment
    st.session_state.generated_script = ""

    return (
        True,
        f"Loaded {len(restored)} components.",
    )
