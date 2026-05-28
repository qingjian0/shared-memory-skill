class MemoryError(Exception): pass
class MemoryNotFoundError(MemoryError): pass
class StorageError(MemoryError): pass
class EmbeddingError(MemoryError): pass
class DecayError(MemoryError): pass
class ContextOverflowError(MemoryError): pass
class SecurityViolationError(MemoryError): pass
class JobQueueFullError(MemoryError): pass
