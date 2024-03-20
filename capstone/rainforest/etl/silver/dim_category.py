from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit
from typing import List, Optional, Type
from dataclasses import asdict
from rainforest.utils.base_table import ETLDataSet, TableETL
from rainforest.etl.bronze.category import CategoryBronzeETL


class DimCategorySilverETL(TableETL):
    def __init__(
        self,
        spark: SparkSession,
        upstream_table_names: Optional[List[Type[TableETL]]] = [CategoryBronzeETL],
        name: str = "dim_category",
        primary_keys: List[str] = ["category_id"],
        storage_path: str = "s3a://rainforest/delta/silver/dim_category",
        data_format: str = "delta",
        database: str = "rainforest",
        partition_keys: List[str] = ["etl_inserted"],
        run_upstream: bool = True,
    ) -> None:
        super().__init__(
            spark,
            upstream_table_names,
            name,
            primary_keys,
            storage_path,
            data_format,
            database,
            partition_keys,
            run_upstream,
        )

    def extract_upstream(self) -> List[ETLDataSet]:
        upstream_etl_datasets = []
        for TableETL in self.upstream_table_names:
            t1 = TableETL(spark=self.spark)
            if self.run_upstream:
                t1.run()
            upstream_etl_datasets.append(t1.read())
        
        return upstream_etl_datasets

    def transform_upstream(self, upstream_datasets: List[ETLDataSet]) -> ETLDataSet:
        category_data = upstream_datasets[0].curr_data
        current_timestamp = datetime.now()

        transformed_data = category_data.withColumn(
            "etl_inserted", lit(current_timestamp)
        )

        # Create a new ETLDataSet instance with the transformed data
        etl_dataset = ETLDataSet(
            name=self.name,
            curr_data=transformed_data,
            primary_keys=self.primary_keys,
            storage_path=self.storage_path,
            data_format=self.data_format,
            database=self.database,
            partition_keys=self.partition_keys,
        )

        return etl_dataset

    def validate(self, data: ETLDataSet) -> bool:
        # Perform any necessary validation checks on the transformed data
        return True

    def load(self, data: ETLDataSet) -> None:
        dim_category_data = data.curr_data

        # Write the transformed data to the Delta Lake table
        dim_category_data.write.option("mergeSchema", "true").format(data.data_format).mode("overwrite").partitionBy(
            data.partition_keys
        ).save(data.storage_path)

    def read(self, partition_keys: Optional[List[str]] = None) -> ETLDataSet:
        # Read the transformed data from the Delta Lake table
        dim_category_data = self.spark.read.format(self.data_format).load(self.storage_path)

        # Select the desired columns
        selected_columns = [
            col('category_id'), 
            col('name').alias('category_name'), 
            col('created_ts'),
            col('last_updated_by'),
            col('last_updated_ts'),
            col('etl_inserted')
        ]

        dim_category_data = dim_category_data.select(selected_columns)

        # Create an ETLDataSet instance
        etl_dataset = ETLDataSet(
            name=self.name,
            curr_data=dim_category_data,
            primary_keys=self.primary_keys,
            storage_path=self.storage_path,
            data_format=self.data_format,
            database=self.database,
            partition_keys=self.partition_keys,
        )

        return etl_dataset
