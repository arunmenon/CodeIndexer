"""
Indexing Observer Pattern

Implements the Observer Pattern for monitoring and reporting indexing pipeline progress.
This allows for real-time visibility into the indexing process, statistical tracking,
and notifications about important events during pipeline execution.
"""

import time
import logging
import json
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field


class IndexingEventType(Enum):
    """Enumeration of indexing event types."""
    PIPELINE_STARTED = auto()
    PIPELINE_COMPLETED = auto()
    PIPELINE_FAILED = auto()
    STAGE_STARTED = auto()
    STAGE_COMPLETED = auto()
    STAGE_FAILED = auto()
    FILE_PROCESSED = auto()
    FILE_FAILED = auto()
    ENTITY_CREATED = auto()
    RELATIONSHIP_CREATED = auto()
    PROGRESS_UPDATE = auto()
    PERFORMANCE_METRIC = auto()
    WARNING = auto()
    ERROR = auto()
    CUSTOM = auto()


@dataclass
class IndexingEvent:
    """
    Represents an event that occurs during the indexing process.
    """
    event_type: IndexingEventType
    source: str
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary representation."""
        return {
            "event_type": self.event_type.name,
            "source": self.source,
            "timestamp": self.timestamp,
            "data": self.data,
            "message": self.message
        }


class IndexingSubject(ABC):
    """
    Abstract Subject class in the Observer Pattern.
    
    Manages observer registrations and notifications.
    """

    def __init__(self):
        """Initialize the subject with empty observers set."""
        self._observers: Set['IndexingObserver'] = set()
        self._logger = logging.getLogger(self.__class__.__name__)

    def attach(self, observer: 'IndexingObserver') -> None:
        """
        Attach an observer to this subject.
        
        Args:
            observer: The observer to attach
        """
        self._observers.add(observer)
        self._logger.debug(f"Observer {observer.__class__.__name__} attached")

    def detach(self, observer: 'IndexingObserver') -> None:
        """
        Detach an observer from this subject.
        
        Args:
            observer: The observer to detach
        """
        try:
            self._observers.remove(observer)
            self._logger.debug(f"Observer {observer.__class__.__name__} detached")
        except KeyError:
            self._logger.warning(f"Observer {observer.__class__.__name__} not found")

    def notify(self, event: IndexingEvent) -> None:
        """
        Notify all observers of an event.
        
        Args:
            event: The event to notify observers about
        """
        for observer in self._observers:
            try:
                observer.update(event)
            except Exception as e:
                self._logger.error(f"Error notifying observer {observer.__class__.__name__}: {e}")


class IndexingObserver(ABC):
    """
    Abstract Observer class in the Observer Pattern.
    
    Receives and processes indexing events.
    """

    @abstractmethod
    def update(self, event: IndexingEvent) -> None:
        """
        Update the observer with a new event.
        
        Args:
            event: The event to process
        """
        pass

    def can_handle_event(self, event_type: IndexingEventType) -> bool:
        """
        Check if this observer can handle a specific event type.
        
        Args:
            event_type: The event type to check
            
        Returns:
            True if this observer can handle the event type, False otherwise
        """
        return True


class ConsoleIndexingObserver(IndexingObserver):
    """
    Indexing observer that logs events to the console.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize console observer.
        
        Args:
            verbose: Whether to log all events or just important ones
        """
        self.verbose = verbose
        self.logger = logging.getLogger(self.__class__.__name__)

    def update(self, event: IndexingEvent) -> None:
        """
        Log indexing event to console.
        
        Args:
            event: The event to log
        """
        # Format timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(event.timestamp))
        
        # Only log important events unless verbose
        if not self.verbose and event.event_type == IndexingEventType.PROGRESS_UPDATE:
            return
            
        # Format message based on event type
        if event.event_type == IndexingEventType.PIPELINE_STARTED:
            message = f"[{timestamp}] Indexing pipeline started: {event.message}"
            self.logger.info(message)
        elif event.event_type == IndexingEventType.PIPELINE_COMPLETED:
            stats = event.data.get("stats", {})
            message = (f"[{timestamp}] Indexing pipeline completed: {event.message} - "
                      f"Processed {stats.get('files_processed', 0)} files, "
                      f"Created {stats.get('entities_created', 0)} entities, "
                      f"Failed {stats.get('files_failed', 0)} files")
            self.logger.info(message)
        elif event.event_type == IndexingEventType.PIPELINE_FAILED:
            message = f"[{timestamp}] ❌ Indexing pipeline failed: {event.message}"
            self.logger.error(message)
        elif event.event_type == IndexingEventType.STAGE_STARTED:
            message = f"[{timestamp}] Stage {event.data.get('stage_name', 'unknown')} started"
            self.logger.info(message)
        elif event.event_type == IndexingEventType.STAGE_COMPLETED:
            stage_time = event.data.get("duration_seconds", 0)
            message = (f"[{timestamp}] Stage {event.data.get('stage_name', 'unknown')} completed "
                      f"in {stage_time:.2f}s")
            self.logger.info(message)
        elif event.event_type == IndexingEventType.PROGRESS_UPDATE:
            progress = event.data.get("progress_percentage", 0)
            message = f"[{timestamp}] Progress: {progress:.1f}% - {event.message}"
            self.logger.info(message)
        elif event.event_type == IndexingEventType.WARNING:
            message = f"[{timestamp}] ⚠️ Warning: {event.message}"
            self.logger.warning(message)
        elif event.event_type == IndexingEventType.ERROR:
            message = f"[{timestamp}] ❌ Error: {event.message}"
            self.logger.error(message)
        else:
            if self.verbose:
                # For other events, just log the message if verbose
                message = f"[{timestamp}] {event.event_type.name}: {event.message}"
                self.logger.debug(message)


class FileIndexingObserver(IndexingObserver):
    """
    Indexing observer that writes events to a file.
    """

    def __init__(self, output_file: str, event_filter: Optional[List[IndexingEventType]] = None):
        """
        Initialize file observer.
        
        Args:
            output_file: Path to the output file
            event_filter: List of event types to record, or None for all events
        """
        self.output_file = output_file
        self.event_filter = event_filter
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Create/clear the output file
        try:
            with open(self.output_file, 'w') as f:
                f.write("# Indexing Events Log\n")
            self.logger.info(f"Initialized file observer writing to {output_file}")
        except Exception as e:
            self.logger.error(f"Error initializing file observer: {e}")

    def update(self, event: IndexingEvent) -> None:
        """
        Write indexing event to file.
        
        Args:
            event: The event to record
        """
        # Check if we should record this event
        if self.event_filter and event.event_type not in self.event_filter:
            return
            
        try:
            # Append the event as JSON
            with open(self.output_file, 'a') as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception as e:
            self.logger.error(f"Error writing event to file: {e}")

    def can_handle_event(self, event_type: IndexingEventType) -> bool:
        """
        Check if this observer can handle a specific event type.
        
        Args:
            event_type: The event type to check
            
        Returns:
            True if this observer can handle the event type, False otherwise
        """
        if self.event_filter is None:
            return True
        return event_type in self.event_filter


class StatisticsIndexingObserver(IndexingObserver):
    """
    Indexing observer that collects and computes statistics.
    """

    def __init__(self):
        """Initialize statistics observer."""
        self.pipeline_start_time: Optional[float] = None
        self.pipeline_end_time: Optional[float] = None
        self.stage_times: Dict[str, float] = {}
        self.stage_start_times: Dict[str, float] = {}
        self.file_count: int = 0
        self.entity_count: int = 0
        self.relationship_count: int = 0
        self.error_count: int = 0
        self.warning_count: int = 0
        self.current_progress: float = 0.0
        self.last_update_time: Optional[float] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def update(self, event: IndexingEvent) -> None:
        """
        Update statistics with a new event.
        
        Args:
            event: The event to process
        """
        # Track pipeline timing
        if event.event_type == IndexingEventType.PIPELINE_STARTED:
            self.pipeline_start_time = event.timestamp
            self.last_update_time = event.timestamp
            
        elif event.event_type == IndexingEventType.PIPELINE_COMPLETED:
            self.pipeline_end_time = event.timestamp
            
        # Track stage timing
        elif event.event_type == IndexingEventType.STAGE_STARTED:
            stage_name = event.data.get("stage_name", "unknown")
            self.stage_start_times[stage_name] = event.timestamp
            
        elif event.event_type == IndexingEventType.STAGE_COMPLETED:
            stage_name = event.data.get("stage_name", "unknown")
            if stage_name in self.stage_start_times:
                duration = event.timestamp - self.stage_start_times[stage_name]
                self.stage_times[stage_name] = duration
            
        # Track counts
        elif event.event_type == IndexingEventType.FILE_PROCESSED:
            self.file_count += 1
            
        elif event.event_type == IndexingEventType.ENTITY_CREATED:
            count = event.data.get("count", 1)
            self.entity_count += count
            
        elif event.event_type == IndexingEventType.RELATIONSHIP_CREATED:
            count = event.data.get("count", 1)
            self.relationship_count += count
            
        elif event.event_type == IndexingEventType.WARNING:
            self.warning_count += 1
            
        elif event.event_type == IndexingEventType.ERROR:
            self.error_count += 1
            
        # Track progress
        elif event.event_type == IndexingEventType.PROGRESS_UPDATE:
            self.current_progress = event.data.get("progress_percentage", self.current_progress)
            self.last_update_time = event.timestamp

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get current statistics.
        
        Returns:
            Dictionary with statistics
        """
        current_time = time.time()
        stats = {
            "file_count": self.file_count,
            "entity_count": self.entity_count,
            "relationship_count": self.relationship_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "progress_percentage": self.current_progress,
            "stage_times": self.stage_times
        }
        
        # Calculate pipeline duration if applicable
        if self.pipeline_start_time:
            if self.pipeline_end_time:
                stats["pipeline_duration_seconds"] = self.pipeline_end_time - self.pipeline_start_time
            else:
                stats["pipeline_duration_seconds"] = current_time - self.pipeline_start_time
        
        # Calculate processing rate if applicable
        if self.file_count > 0 and self.pipeline_start_time:
            duration = (self.pipeline_end_time or current_time) - self.pipeline_start_time
            if duration > 0:
                stats["files_per_second"] = self.file_count / duration
                stats["entities_per_second"] = self.entity_count / duration
        
        # Calculate estimated time remaining if in progress
        if self.pipeline_start_time and not self.pipeline_end_time and self.current_progress > 0:
            elapsed = current_time - self.pipeline_start_time
            if self.current_progress < 100:
                estimated_total = elapsed / (self.current_progress / 100)
                stats["estimated_seconds_remaining"] = max(0, estimated_total - elapsed)
            else:
                stats["estimated_seconds_remaining"] = 0
        
        return stats


class CallbackIndexingObserver(IndexingObserver):
    """
    Indexing observer that calls a provided callback function for events.
    """

    def __init__(self, callback: Callable[[IndexingEvent], None], 
                 event_filter: Optional[List[IndexingEventType]] = None):
        """
        Initialize callback observer.
        
        Args:
            callback: Function to call for each event
            event_filter: List of event types to process, or None for all events
        """
        self.callback = callback
        self.event_filter = event_filter
        self.logger = logging.getLogger(self.__class__.__name__)

    def update(self, event: IndexingEvent) -> None:
        """
        Process event by calling the callback function.
        
        Args:
            event: The event to process
        """
        # Check if we should process this event
        if self.event_filter and event.event_type not in self.event_filter:
            return
            
        try:
            # Call the callback with the event
            self.callback(event)
        except Exception as e:
            self.logger.error(f"Error in callback: {e}")

    def can_handle_event(self, event_type: IndexingEventType) -> bool:
        """
        Check if this observer can handle a specific event type.
        
        Args:
            event_type: The event type to check
            
        Returns:
            True if this observer can handle the event type, False otherwise
        """
        if self.event_filter is None:
            return True
        return event_type in self.event_filter


class ProgressBarIndexingObserver(IndexingObserver):
    """
    Indexing observer that displays a progress bar.
    
    This is a simplified implementation that updates a terminal-based
    progress bar. In a real-world application, you might use a library
    like tqdm or a more sophisticated UI component.
    """

    def __init__(self, update_interval: float = 0.5):
        """
        Initialize progress bar observer.
        
        Args:
            update_interval: Minimum time in seconds between progress bar updates
        """
        self.update_interval = update_interval
        self.last_update_time = 0
        self.progress = 0
        self.message = ""
        self.show_progress_bar = True
        self.logger = logging.getLogger(self.__class__.__name__)

    def update(self, event: IndexingEvent) -> None:
        """
        Update progress bar based on event.
        
        Args:
            event: The event to process
        """
        current_time = time.time()
        
        # Handle pipeline events that affect the progress bar visibility
        if event.event_type == IndexingEventType.PIPELINE_STARTED:
            self.progress = 0
            self.message = event.message
            self._render_progress_bar()
            self.last_update_time = current_time
            
        elif event.event_type == IndexingEventType.PIPELINE_COMPLETED:
            self.progress = 100
            self.message = event.message
            self._render_progress_bar()
            self.last_update_time = current_time
            print()  # Add newline after completed progress
            
        elif event.event_type == IndexingEventType.PIPELINE_FAILED:
            self.message = f"Failed: {event.message}"
            self._render_progress_bar()
            self.last_update_time = current_time
            print()  # Add newline after failed progress
            
        # Update progress based on progress events
        elif event.event_type == IndexingEventType.PROGRESS_UPDATE:
            # Only update if enough time has passed since the last update
            if current_time - self.last_update_time >= self.update_interval:
                self.progress = event.data.get("progress_percentage", self.progress)
                self.message = event.message
                self._render_progress_bar()
                self.last_update_time = current_time

    def _render_progress_bar(self) -> None:
        """Render the progress bar to the console."""
        try:
            # Get terminal width (fallback to 80 if can't determine)
            try:
                import shutil
                term_width = shutil.get_terminal_size().columns
            except (ImportError, AttributeError):
                term_width = 80
            
            # Calculate bar width (leaving room for percentage and message)
            bar_width = term_width - 20  # Leave room for other elements
            bar_width = max(10, bar_width)  # Ensure minimum width
            
            # Calculate the number of filled positions
            filled_width = int(self.progress / 100 * bar_width)
            
            # Create the progress bar
            bar = f"[{'#' * filled_width}{' ' * (bar_width - filled_width)}]"
            
            # Format the output line
            line = f"\r{bar} {self.progress:5.1f}% {self.message}"
            
            # Truncate if too long for terminal
            if len(line) > term_width:
                line = line[:term_width-3] + "..."
            
            # Print without newline to update in-place
            print(line, end="", flush=True)
            
        except Exception as e:
            self.logger.error(f"Error rendering progress bar: {e}")

    def can_handle_event(self, event_type: IndexingEventType) -> bool:
        """
        Check if this observer can handle a specific event type.
        
        Args:
            event_type: The event type to check
            
        Returns:
            True if this observer can handle the event type, False otherwise
        """
        # Only handle events relevant to the progress bar
        return event_type in [
            IndexingEventType.PIPELINE_STARTED,
            IndexingEventType.PIPELINE_COMPLETED,
            IndexingEventType.PIPELINE_FAILED,
            IndexingEventType.PROGRESS_UPDATE
        ]


class IndexingObserverManager:
    """
    Manager for indexing observers.
    
    This class provides a centralized point for managing observers
    and facilitates easy integration with existing code.
    """

    def __init__(self):
        """Initialize the observer manager."""
        self.observers: List[IndexingObserver] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_observer(self, observer: IndexingObserver) -> None:
        """
        Add an observer.
        
        Args:
            observer: The observer to add
        """
        self.observers.append(observer)
        self.logger.debug(f"Added observer: {observer.__class__.__name__}")

    def remove_observer(self, observer: IndexingObserver) -> None:
        """
        Remove an observer.
        
        Args:
            observer: The observer to remove
        """
        if observer in self.observers:
            self.observers.remove(observer)
            self.logger.debug(f"Removed observer: {observer.__class__.__name__}")

    def clear_observers(self) -> None:
        """Remove all observers."""
        self.observers.clear()
        self.logger.debug("Cleared all observers")

    def notify_observers(self, event: IndexingEvent) -> None:
        """
        Notify all observers of an event.
        
        Args:
            event: The event to notify observers about
        """
        for observer in self.observers:
            try:
                if observer.can_handle_event(event.event_type):
                    observer.update(event)
            except Exception as e:
                self.logger.error(f"Error notifying observer {observer.__class__.__name__}: {e}")

    def create_pipeline_started_event(self, source: str, repository: str) -> IndexingEvent:
        """
        Create a pipeline started event.
        
        Args:
            source: Source of the event
            repository: Repository being indexed
            
        Returns:
            Pipeline started event
        """
        return IndexingEvent(
            event_type=IndexingEventType.PIPELINE_STARTED,
            source=source,
            message=f"Starting indexing for repository: {repository}",
            data={"repository": repository}
        )

    def create_pipeline_completed_event(self, source: str, repository: str, stats: Dict[str, Any]) -> IndexingEvent:
        """
        Create a pipeline completed event.
        
        Args:
            source: Source of the event
            repository: Repository being indexed
            stats: Statistics about the indexing process
            
        Returns:
            Pipeline completed event
        """
        return IndexingEvent(
            event_type=IndexingEventType.PIPELINE_COMPLETED,
            source=source,
            message=f"Completed indexing for repository: {repository}",
            data={"repository": repository, "stats": stats}
        )

    def create_pipeline_failed_event(self, source: str, repository: str, error: str) -> IndexingEvent:
        """
        Create a pipeline failed event.
        
        Args:
            source: Source of the event
            repository: Repository being indexed
            error: Error message
            
        Returns:
            Pipeline failed event
        """
        return IndexingEvent(
            event_type=IndexingEventType.PIPELINE_FAILED,
            source=source,
            message=f"Failed indexing for repository: {repository}",
            data={"repository": repository, "error": error}
        )

    def create_progress_event(self, source: str, percentage: float, message: str = "") -> IndexingEvent:
        """
        Create a progress update event.
        
        Args:
            source: Source of the event
            percentage: Progress percentage (0-100)
            message: Optional progress message
            
        Returns:
            Progress update event
        """
        return IndexingEvent(
            event_type=IndexingEventType.PROGRESS_UPDATE,
            source=source,
            message=message,
            data={"progress_percentage": percentage}
        )

    def create_stage_started_event(self, source: str, stage_name: str) -> IndexingEvent:
        """
        Create a stage started event.
        
        Args:
            source: Source of the event
            stage_name: Name of the stage
            
        Returns:
            Stage started event
        """
        return IndexingEvent(
            event_type=IndexingEventType.STAGE_STARTED,
            source=source,
            message=f"Starting stage: {stage_name}",
            data={"stage_name": stage_name}
        )

    def create_stage_completed_event(self, source: str, stage_name: str, duration: float) -> IndexingEvent:
        """
        Create a stage completed event.
        
        Args:
            source: Source of the event
            stage_name: Name of the stage
            duration: Duration of the stage in seconds
            
        Returns:
            Stage completed event
        """
        return IndexingEvent(
            event_type=IndexingEventType.STAGE_COMPLETED,
            source=source,
            message=f"Completed stage: {stage_name}",
            data={"stage_name": stage_name, "duration_seconds": duration}
        )
        
    def create_file_processed_event(self, source: str, file_path: str, file_id: str) -> IndexingEvent:
        """
        Create a file processed event.
        
        Args:
            source: Source of the event
            file_path: Path to the processed file
            file_id: ID of the processed file
            
        Returns:
            File processed event
        """
        return IndexingEvent(
            event_type=IndexingEventType.FILE_PROCESSED,
            source=source,
            message=f"Processed file: {file_path}",
            data={"file_path": file_path, "file_id": file_id}
        )
        
    def create_error_event(self, source: str, error_message: str, details: Dict[str, Any] = None) -> IndexingEvent:
        """
        Create an error event.
        
        Args:
            source: Source of the event
            error_message: Error message
            details: Optional error details
            
        Returns:
            Error event
        """
        return IndexingEvent(
            event_type=IndexingEventType.ERROR,
            source=source,
            message=error_message,
            data=details or {}
        )
        
    def create_custom_event(self, source: str, message: str, data: Dict[str, Any] = None) -> IndexingEvent:
        """
        Create a custom event.
        
        Args:
            source: Source of the event
            message: Event message
            data: Optional event data
            
        Returns:
            Custom event
        """
        return IndexingEvent(
            event_type=IndexingEventType.CUSTOM,
            source=source,
            message=message,
            data=data or {}
        )