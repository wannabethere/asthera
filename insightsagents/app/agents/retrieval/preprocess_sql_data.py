import logging
from typing import Dict, Optional

import tiktoken

logger = logging.getLogger("genieml-agents")


class PreprocessSqlData:
    """Preprocesses SQL data to ensure it fits within token limits."""
    
    def __init__(
        self,
        model: str,
        max_tokens: int = 100_000,
        max_iterations: int = 1000,
        reduction_step: int = 50,
    ) -> None:
        """Initialize the SQL data preprocessor.
        
        Args:
            model: The LLM model name to determine encoding
            max_tokens: Maximum number of tokens allowed
            max_iterations: Maximum number of reduction iterations
            reduction_step: Number of rows to remove in each reduction step
        """
        self._max_tokens = max_tokens
        self._max_iterations = max_iterations
        self._reduction_step = reduction_step
        
        # Set encoding based on model
        if model in ["gpt-4o-mini", "gpt-4o"]:
            self._encoding = tiktoken.get_encoding("o200k_base")
        else:
            self._encoding = tiktoken.get_encoding("cl100k_base")

    def _reduce_data_size(self, data: list) -> list:
        """Reduce the size of data by removing elements from the end.
        
        Args:
            data: The input list to reduce
            
        Returns:
            A list with reduced size
            
        Raises:
            ValueError: If reduction_step is not positive
        """
        if self._reduction_step <= 0:
            raise ValueError("reduction_step must be positive")

        elements_to_keep = max(0, len(data) - self._reduction_step)
        returned_data = data[:elements_to_keep]

        logger.info(
            f"Reducing data size by {self._reduction_step} rows. "
            f"Original size: {len(data)}, New size: {len(returned_data)}"
        )

        return returned_data

    def run(self, sql_data: Dict) -> Dict:
        """Preprocess SQL data to fit within token limits.
        
        Args:
            sql_data: Dictionary containing SQL data to preprocess
            
        Returns:
            Dictionary containing:
            - sql_data: Preprocessed SQL data
            - num_rows_used_in_llm: Number of rows used after preprocessing
            - tokens: Final token count
        """
        logger.info("Preprocessing SQL data...")
        
        try:
            token_count = len(self._encoding.encode(str(sql_data)))
            num_rows_used_in_llm = len(sql_data.get("data", []))
            iteration = 0

            while token_count > self._max_tokens:
                if iteration >= self._max_iterations:
                    logger.warning(
                        f"Reached maximum iterations ({self._max_iterations}). "
                        "Stopping preprocessing."
                    )
                    break

                iteration += 1
                data = sql_data.get("data", [])
                sql_data["data"] = self._reduce_data_size(data)
                num_rows_used_in_llm = len(sql_data.get("data", []))
                token_count = len(self._encoding.encode(str(sql_data)))
                logger.info(f"Token count: {token_count}")

            return {
                "sql_data": sql_data,
                "num_rows_used_in_llm": num_rows_used_in_llm,
                "tokens": token_count,
            }
            
        except Exception as e:
            logger.error(f"Error preprocessing SQL data: {str(e)}")
            return {
                "sql_data": sql_data,
                "num_rows_used_in_llm": 0,
                "tokens": 0,
            }


if __name__ == "__main__":
    # Example usage
    processor = PreprocessSqlData(
        model="gpt-4",
        max_tokens=100_000,
        max_iterations=1000,
        reduction_step=50
    )
    
    # Example SQL data
    sql_data = {
        "data": [{"row": i} for i in range(1000)],
        "metadata": {"table": "example"}
    }
    
    # Process the data
    result = processor.run(sql_data)
    print(f"Preprocessed SQL data: {result}")
