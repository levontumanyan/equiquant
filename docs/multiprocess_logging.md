# Multiprocess Logging Architecture

In EquiQuant, parallel data fetching runs within child processes spawned via `ProcessPoolExecutor` to ensure high throughput and prevent thread/signal conflicts. However, because worker processes run in isolated environments under the `spawn` context, they do not inherit the main process's active logging handlers (such as the rotating file handler for `logs/server.log`).

This document details the centralized queue-based logging architecture used to securely route subprocess logs back to the main process without causing file descriptor conflicts or resource leaks.

# Core Concepts

Centralized logging across subprocesses leverages a thread-safe queue and listener pipeline:

* **Central Queue**: A `multiprocessing.Queue` (created using the `spawn` start method context) acts as the inter-process communication (IPC) channel.
* **Worker QueueHandler**: Inside each worker process, standard handlers are removed from the root logger, and a `logging.handlers.QueueHandler` is attached. Any log messages emitted in the subprocess are serialized and sent over the central queue.
* **Main Process QueueListener**: A background `logging.handlers.QueueListener` thread drains the queue in the main process.
* **Custom Dispatcher**: A custom `LogQueueDispatcher` forwards logs from the listener back into the main process's logging pipeline, letting them propagate normally to `logs/server.log` and console outputs.

# Logging Pipeline Diagram

The following D2 diagram represents the log routing flow from worker processes to the main process's logger and handlers:

```d2
main_process: Main Process {
  api: API / Uvicorn
  fetch_data: "fetch_data()" {
    queue_listener: QueueListener
  }
  dispatcher: LogQueueDispatcher
  root_logger: Root Logger
  server_log: "logs/server.log"
  stdout: stdout / stderr
  
  queue_listener -> dispatcher: "Drains records"
  dispatcher -> root_logger: "Forwards records via handle()"
  root_logger -> server_log: "RotatingFileHandler"
  root_logger -> stdout: "StreamHandler"
}

worker_processes: Worker Processes {
  worker_1: Worker Process 1 {
    logger_1: Logger
    queue_handler_1: QueueHandler
    
    logger_1 -> queue_handler_1: "Route record"
  }
  
  worker_2: Worker Process 2 {
    logger_2: Logger
    queue_handler_2: QueueHandler
    
    logger_2 -> queue_handler_2: "Route record"
  }
}

worker_processes.worker_1.queue_handler_1 -> main_process.fetch_data.queue_listener: "IPC Queue"
worker_processes.worker_2.queue_handler_2 -> main_process.fetch_data.queue_listener: "IPC Queue"
```

# Best Practices

EquiQuant follows standard Python logging best practices to ensure stability and correctness:

* **Never Write to One File From Multiple Processes**: Operating systems handle concurrent writes to the same file differently. Without locks, log entries interleave, truncate, or fail completely. Centralizing to a single writer process avoids file locking issues.
* **Non-Blocking Worker Logs**: Workers push log messages to an in-memory queue, which is extremely fast and prevents file write latency from delaying worker fetch routines.
* **Process Start Method Safety**: Always use a clean start context (`multiprocessing.get_context("spawn").Queue()`) to ensure compatibility and robustness across macOS, Linux, and Windows platforms.
* **Unified Formatting**: Formatting is applied in the main process, ensuring JSON-structured logs in `logs/server.log` remain consistent regardless of which worker emitted them.
