"""
Batch Processor

A module for efficient batch processing of operations with different strategies.
Implements the Factory Pattern to create appropriate batch processors based on
the type of operation and desired strategy.
"""

from abc import ABC, abstractmethod
import logging
import os
import concurrent.futures
from typing import List, Dict, Any, Callable, Optional, TypeVar, Generic, Union, Iterable

# Type variables for generic typing
T = TypeVar('T')  # Input type
R = TypeVar('R')  # Result type

class BatchProcessor(Generic[T, R], ABC):
    """
    Abstract base class for batch processors.
    
    Implements the Template Method pattern for batch processing with hooks for
    specific processing strategies to override.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the batch processor.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self.batch_size = self.config.get("batch_size", 100)
        self.max_workers = self.config.get("max_workers", os.cpu_count())
        self.results = []
        self.errors = []
    
    @abstractmethod
    def process_batch(self, batch: List[T]) -> List[R]:
        """
        Process a batch of items.
        
        Args:
            batch: List of items to process
            
        Returns:
            List of processing results
        """
        pass
    
    def pre_process(self, items: List[T]) -> List[T]:
        """
        Hook for pre-processing before batch processing.
        
        Args:
            items: List of items to pre-process
            
        Returns:
            Pre-processed items
        """
        return items
    
    def post_process(self, results: List[R]) -> List[R]:
        """
        Hook for post-processing after batch processing.
        
        Args:
            results: List of processing results
            
        Returns:
            Post-processed results
        """
        return results
    
    def on_batch_complete(self, batch_index: int, batch_results: List[R]) -> None:
        """
        Hook called when a batch is complete.
        
        Args:
            batch_index: Index of the completed batch
            batch_results: Results from the batch
        """
        self.logger.debug(f"Completed batch {batch_index} with {len(batch_results)} results")
    
    def on_error(self, item: T, error: Exception) -> None:
        """
        Hook called when an error occurs during processing.
        
        Args:
            item: Item that caused the error
            error: The exception that occurred
        """
        self.logger.error(f"Error processing item: {error}")
        self.errors.append({"item": item, "error": str(error)})
    
    def process(self, items: List[T]) -> Dict[str, Any]:
        """
        Process a list of items in batches.
        
        Args:
            items: List of items to process
            
        Returns:
            Dictionary with processing results and stats
        """
        self.logger.info(f"Starting batch processing of {len(items)} items with batch size {self.batch_size}")
        
        # Pre-process items
        processed_items = self.pre_process(items)
        
        # Split into batches
        batches = [processed_items[i:i + self.batch_size] for i in range(0, len(processed_items), self.batch_size)]
        self.logger.info(f"Split into {len(batches)} batches")
        
        # Process each batch
        all_results = []
        for i, batch in enumerate(batches):
            try:
                batch_results = self.process_batch(batch)
                all_results.extend(batch_results)
                self.on_batch_complete(i, batch_results)
            except Exception as e:
                self.logger.error(f"Error processing batch {i}: {e}")
                # Continue with next batch instead of failing entirely
                continue
        
        # Post-process results
        final_results = self.post_process(all_results)
        self.results = final_results
        
        # Return results and stats
        return {
            "results": final_results,
            "total_processed": len(final_results),
            "total_items": len(items),
            "errors": self.errors,
            "error_count": len(self.errors)
        }


class SequentialBatchProcessor(BatchProcessor[T, R]):
    """
    A batch processor that processes items sequentially.
    """
    
    def __init__(self, process_func: Callable[[T], R], config: Dict[str, Any] = None):
        """
        Initialize the sequential batch processor.
        
        Args:
            process_func: Function to process each item
            config: Configuration dictionary
        """
        super().__init__(config)
        self.process_func = process_func
    
    def process_batch(self, batch: List[T]) -> List[R]:
        """
        Process a batch of items sequentially.
        
        Args:
            batch: List of items to process
            
        Returns:
            List of processing results
        """
        results = []
        for item in batch:
            try:
                result = self.process_func(item)
                results.append(result)
            except Exception as e:
                self.on_error(item, e)
        return results


class ParallelBatchProcessor(BatchProcessor[T, R]):
    """
    A batch processor that processes items in parallel using a thread pool.
    
    Suitable for I/O-bound operations.
    """
    
    def __init__(self, process_func: Callable[[T], R], config: Dict[str, Any] = None):
        """
        Initialize the parallel batch processor.
        
        Args:
            process_func: Function to process each item
            config: Configuration dictionary
        """
        super().__init__(config)
        self.process_func = process_func
    
    def process_batch(self, batch: List[T]) -> List[R]:
        """
        Process a batch of items in parallel using a thread pool.
        
        Args:
            batch: List of items to process
            
        Returns:
            List of processing results
        """
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks and map futures to their corresponding items
            future_to_item = {executor.submit(self.process_func, item): item for item in batch}
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    self.on_error(item, e)
        
        return results


class MultiprocessBatchProcessor(BatchProcessor[T, R]):
    """
    A batch processor that processes items in parallel using a process pool.
    
    Suitable for CPU-bound operations.
    """
    
    def __init__(self, process_func: Callable[[T], R], config: Dict[str, Any] = None):
        """
        Initialize the multiprocess batch processor.
        
        Args:
            process_func: Function to process each item
            config: Configuration dictionary
        """
        super().__init__(config)
        self.process_func = process_func
    
    def process_batch(self, batch: List[T]) -> List[R]:
        """
        Process a batch of items in parallel using a process pool.
        
        Args:
            batch: List of items to process
            
        Returns:
            List of processing results
        """
        results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks and map futures to their corresponding items
            future_to_item = {executor.submit(self.process_func, item): item for item in batch}
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    self.on_error(item, e)
        
        return results


class ChunkedBatchProcessor(BatchProcessor[T, R]):
    """
    A batch processor that divides work into chunks for processing by worker processes.
    
    This approach is more efficient for large numbers of small items, as it reduces
    the overhead of task submission and result collection.
    """
    
    def __init__(self, process_func: Callable[[List[T]], List[R]], config: Dict[str, Any] = None):
        """
        Initialize the chunked batch processor.
        
        Args:
            process_func: Function to process a chunk of items
            config: Configuration dictionary
        """
        super().__init__(config)
        self.process_func = process_func
        self.chunk_size = self.config.get("chunk_size", 10)  # Items per chunk
    
    def process_batch(self, batch: List[T]) -> List[R]:
        """
        Process a batch of items in chunks using a process pool.
        
        Args:
            batch: List of items to process
            
        Returns:
            List of processing results
        """
        # Create chunks
        chunks = [batch[i:i + self.chunk_size] for i in range(0, len(batch), self.chunk_size)]
        chunk_count = len(chunks)
        
        self.logger.debug(f"Processing batch with {chunk_count} chunks of size {self.chunk_size}")
        
        # Process chunks in parallel
        all_results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.process_func, chunk) for chunk in chunks]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    chunk_results = future.result()
                    all_results.extend(chunk_results)
                except Exception as e:
                    self.logger.error(f"Error processing chunk: {e}")
        
        return all_results


class DatabaseBatchProcessor(BatchProcessor[T, R]):
    """
    A specialized batch processor for database operations.
    
    Implements efficient batching for database operations, with transaction
    management and bulk operations.
    """
    
    def __init__(self, db_connector: Any, operation_func: Callable[[Any, List[T]], List[R]], 
                config: Dict[str, Any] = None):
        """
        Initialize the database batch processor.
        
        Args:
            db_connector: Database connector object
            operation_func: Function that performs the database operation
            config: Configuration dictionary
        """
        super().__init__(config)
        self.db_connector = db_connector
        self.operation_func = operation_func
        self.use_transactions = self.config.get("use_transactions", True)
    
    def process_batch(self, batch: List[T]) -> List[R]:
        """
        Process a batch of database operations.
        
        Args:
            batch: List of items to process
            
        Returns:
            List of processing results
        """
        try:
            if self.use_transactions:
                # Execute in a single transaction if supported
                if hasattr(self.db_connector, 'begin_transaction'):
                    with self.db_connector.begin_transaction() as tx:
                        results = self.operation_func(self.db_connector, batch)
                else:
                    # Fall back to regular processing
                    results = self.operation_func(self.db_connector, batch)
            else:
                # Execute without transaction
                results = self.operation_func(self.db_connector, batch)
                
            return results
        except Exception as e:
            self.logger.error(f"Database batch operation failed: {e}")
            # Re-raise to be caught by the main process method
            raise


class BatchProcessorFactory:
    """
    Factory for creating batch processors based on the type of operation.
    
    Implements the Factory Pattern to create the appropriate batch processor
    based on the processing requirements.
    """
    
    @staticmethod
    def create_processor(processor_type: str, process_func: Callable, 
                          config: Dict[str, Any] = None) -> BatchProcessor:
        """
        Create a batch processor of the specified type.
        
        Args:
            processor_type: Type of processor to create
                ("sequential", "parallel", "multiprocess", "chunked", "database")
            process_func: Function to process items
            config: Configuration dictionary
            
        Returns:
            A batch processor instance
        """
        config = config or {}
        
        if processor_type == "sequential":
            return SequentialBatchProcessor(process_func, config)
        elif processor_type == "parallel":
            return ParallelBatchProcessor(process_func, config)
        elif processor_type == "multiprocess":
            return MultiprocessBatchProcessor(process_func, config)
        elif processor_type == "chunked":
            return ChunkedBatchProcessor(process_func, config)
        elif processor_type == "database":
            # For database processor, process_func should be operation_func
            # and config should contain db_connector
            db_connector = config.get("db_connector")
            if not db_connector:
                raise ValueError("Database connector required for database batch processor")
            return DatabaseBatchProcessor(db_connector, process_func, config)
        else:
            raise ValueError(f"Unknown processor type: {processor_type}")