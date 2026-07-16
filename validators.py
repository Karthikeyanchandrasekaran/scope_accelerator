from typing import Any


DATASET_PRODUCING_COMPONENTS = {
    "Read File": "dataset_name",
    "Select Columns": "output_dataset",
    "Filter": "output_dataset",
    "Join": "output_dataset",
    "Aggregate": "output_dataset",
    "Union": "output_dataset",
}


def validate_join_source(
    label: str,
    source_type: str,
    dataset_name: str,
    subquery: str,
    available_datasets: set[str],
    errors: list[str],
) -> None:
    if source_type == "Dataset":
        if not dataset_name:
            errors.append(
                f"{label}: dataset is required."
            )
        elif dataset_name not in available_datasets:
            errors.append(
                f"{label}: dataset "
                f"'{dataset_name}' is not available."
            )

    elif source_type == "Subquery":
        if not subquery.strip():
            errors.append(
                f"{label}: subquery is required."
            )

    else:
        errors.append(
            f"{label}: unsupported source type "
            f"'{source_type}'."
        )


def validate_workflow(
    components: list[dict[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[str] = []

    available_datasets: set[str] = set()
    declared_variables: set[str] = set()

    if not components:
        errors.append(
            "Add at least one component."
        )

    for position, component in enumerate(
        components,
        start=1,
    ):
        component_type = component.get(
            "type",
            "",
        )

        config = component.get(
            "config",
            {},
        )

        label = (
            f"Step {position} "
            f"({component_type})"
        )

        if component_type == "Declare Variable":
            variable_name = config.get(
                "variable_name",
                "",
            ).strip()

            if not variable_name:
                errors.append(
                    f"{label}: variable name is required."
                )

            elif variable_name in declared_variables:
                errors.append(
                    f"{label}: duplicate variable "
                    f"'{variable_name}'."
                )

            else:
                declared_variables.add(
                    variable_name
                )

        elif component_type == "Read File":
            dataset_name = config.get(
                "dataset_name",
                "",
            ).strip()

            if not dataset_name:
                errors.append(
                    f"{label}: dataset name is required."
                )

            if not config.get(
                "input_path",
                "",
            ).strip():
                errors.append(
                    f"{label}: input path is required."
                )

            if not config.get("schema"):
                errors.append(
                    f"{label}: schema is required."
                )

        elif component_type in {
            "Select Columns",
            "Filter",
            "Aggregate",
        }:
            source_dataset = config.get(
                "source_dataset",
                "",
            )

            if (
                source_dataset
                not in available_datasets
            ):
                errors.append(
                    f"{label}: source dataset "
                    f"'{source_dataset}' is unavailable."
                )

        elif component_type == "Join":
            validate_join_source(
                label=f"{label} left source",
                source_type=config.get(
                    "left_source_type",
                    "Dataset",
                ),
                dataset_name=config.get(
                    "left_dataset",
                    "",
                ),
                subquery=config.get(
                    "left_subquery",
                    "",
                ),
                available_datasets=available_datasets,
                errors=errors,
            )

            validate_join_source(
                label=f"{label} right source",
                source_type=config.get(
                    "right_source_type",
                    "Dataset",
                ),
                dataset_name=config.get(
                    "right_dataset",
                    "",
                ),
                subquery=config.get(
                    "right_subquery",
                    "",
                ),
                available_datasets=available_datasets,
                errors=errors,
            )

            if not config.get(
                "join_condition",
                "",
            ).strip():
                errors.append(
                    f"{label}: join condition is required."
                )

            if not config.get(
                "output_dataset",
                "",
            ).strip():
                errors.append(
                    f"{label}: output dataset is required."
                )

        elif component_type == "Union":
            for key in [
                "left_dataset",
                "right_dataset",
            ]:
                dataset_name = config.get(
                    key,
                    "",
                )

                if (
                    dataset_name
                    not in available_datasets
                ):
                    errors.append(
                        f"{label}: dataset "
                        f"'{dataset_name}' is unavailable."
                    )

        elif component_type == "Write File":
            source_dataset = config.get(
                "source_dataset",
                "",
            )

            if (
                source_dataset
                not in available_datasets
            ):
                errors.append(
                    f"{label}: output source "
                    f"'{source_dataset}' is unavailable."
                )

            if not config.get(
                "output_path",
                "",
            ).strip():
                errors.append(
                    f"{label}: output path is required."
                )

        output_field = (
            DATASET_PRODUCING_COMPONENTS.get(
                component_type
            )
        )

        if output_field:
            output_dataset = config.get(
                output_field,
                "",
            ).strip()

            if output_dataset:
                if output_dataset in available_datasets:
                    warnings.append(
                        f"{label}: dataset "
                        f"'{output_dataset}' is overwritten."
                    )

                available_datasets.add(
                    output_dataset
                )

    if not any(
        component.get("type") == "Write File"
        for component in components
    ):
        warnings.append(
            "Workflow has no Write File component."
        )

    if components:
        checks.append(
            f"{len(components)} components configured."
        )

        checks.append(
            f"{len(available_datasets)} datasets produced."
        )

    return {
        "is_valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }
