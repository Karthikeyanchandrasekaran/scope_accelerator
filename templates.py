WORKFLOW_TEMPLATES = {
    "Simple Read and Write": {
        "job_name": "SimpleReadWrite",
        "environment": "DEV",
        "components": [
            {
                "id": 1,
                "type": "Read File",
                "config": {
                    "dataset_name": "source_data",
                    "input_path": "/data/raw/input.csv",
                    "extractor": "DefaultTextExtractor",
                    "delimiter": ",",
                    "skip_header": True,
                    "schema": [
                        {
                            "name": "Id",
                            "type": "string",
                        },
                        {
                            "name": "Value",
                            "type": "int",
                        },
                    ],
                },
            },
            {
                "id": 2,
                "type": "Write File",
                "config": {
                    "source_dataset": "source_data",
                    "output_path": "/data/output/result.csv",
                    "outputter": "DefaultTextOutputter",
                    "delimiter": ",",
                    "include_header": True,
                },
            },
        ],
    },
    "Dataset and Subquery Join": {
        "job_name": "CustomerUsageJoin",
        "environment": "DEV",
        "components": [
            {
                "id": 1,
                "type": "Read File",
                "config": {
                    "dataset_name": "customer_data",
                    "input_path": "/data/raw/customers.csv",
                    "extractor": "DefaultTextExtractor",
                    "delimiter": ",",
                    "skip_header": True,
                    "schema": [
                        {
                            "name": "CustomerId",
                            "type": "string",
                        },
                        {
                            "name": "ProductId",
                            "type": "string",
                        },
                    ],
                },
            },
            {
                "id": 2,
                "type": "Join",
                "config": {
                    "left_source_type": "Dataset",
                    "left_dataset": "customer_data",
                    "left_subquery": "",
                    "left_alias": "customer",

                    "right_source_type": "Subquery",
                    "right_dataset": "",
                    "right_subquery": (
                        "SELECT\n"
                        "    ProductId,\n"
                        "    ProductName\n"
                        "FROM product_data\n"
                        "WHERE IsActive == true"
                    ),
                    "right_subquery_columns": [
                        "ProductId",
                        "ProductName",
                    ],
                    "right_alias": "product",

                    "join_type": "LEFT OUTER",
                    "join_condition": (
                        "customer.ProductId == "
                        "product.ProductId"
                    ),
                    "selected_columns": [
                        "customer.CustomerId",
                        "customer.ProductId",
                        "product.ProductName",
                    ],
                    "selected_column_names": [
                        "CustomerId",
                        "ProductId",
                        "ProductName",
                    ],
                    "output_dataset": "joined_data",
                },
            },
            {
                "id": 3,
                "type": "Write File",
                "config": {
                    "source_dataset": "joined_data",
                    "output_path": (
                        "/data/output/"
                        "customer_product.csv"
                    ),
                    "outputter": "DefaultTextOutputter",
                    "delimiter": ",",
                    "include_header": True,
                },
            },
        ],
    },
}
