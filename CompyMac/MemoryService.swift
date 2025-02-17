//
//  MemoryService.swift
//  compymac
//
//  Memory service for handling WebSocket-based memory operations.
//

import Foundation

/// Memory service singleton for handling memory operations.
class MemoryService {
    /// Shared instance for singleton access.
    static let shared = MemoryService()
    
    /// Python service for WebSocket communication.
    private let pythonService = PythonBrowserService.shared
    private let pythonService: PythonBrowserService
    
    /// Private initializer for singleton pattern.
    private init() {
        pythonService = PythonBrowserService.shared
    }
    
    /// Store a new memory with content and metadata.
    ///
    /// - Parameters:
    ///   - content: Raw memory content
    ///   - metadata: Additional memory metadata
    ///   - completion: Completion handler with Result type
    func storeMemory(
        _ content: String,
        metadata: [String: Any],
        completion: @escaping (Result<[String: Any], Error>) -> Void
    ) {
        let payload: [String: Any] = [
            "action": "store_memory",
            "content": content,
            "metadata": metadata,
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]
        
        pythonService.sendCommand(payload) { result in
            switch result {
            case .success(let response):
                guard let memoryData = response as? [String: Any] else {
                    completion(.failure(MemoryError.invalidResponse))
                    return
                }
                completion(.success(memoryData))
            case .failure(let error):
                completion(.failure(error))
            }
        }
    }
    
    /// Retrieve context using hybrid query approach.
    ///
    /// - Parameters:
    ///   - query: Search query for semantic similarity
    ///   - taskId: Optional task-specific context ID
    ///   - timeRange: Optional time range filter (e.g., "1d", "7d")
    ///   - completion: Completion handler with Result type
    func retrieveContext(
        query: String,
        taskId: String? = nil,
        timeRange: String? = nil,
        completion: @escaping (Result<[[String: Any]], Error>) -> Void
    ) {
        var filters: [String: Any] = [:]
        if let taskId = taskId {
            filters["task_id"] = taskId
        }
        if let timeRange = timeRange {
            filters["time_range"] = timeRange
        }
        
        let payload: [String: Any] = [
            "action": "retrieve_context",
            "query": query,
            "filters": filters
        ]
        
        pythonService.sendCommand(payload) { result in
            switch result {
            case .success(let response):
                guard let contextData = response as? [[String: Any]] else {
                    completion(.failure(MemoryError.invalidResponse))
                    return
                }
                completion(.success(contextData))
            case .failure(let error):
                completion(.failure(error))
            }
        }
    }
    
    /// Update an existing memory record.
    ///
    /// - Parameters:
    ///   - memoryId: ID of the memory to update
    ///   - updates: Dictionary of fields to update
    ///   - completion: Completion handler with Result type
    func updateMemory(
        _ memoryId: String,
        updates: [String: Any],
        completion: @escaping (Result<[String: Any], Error>) -> Void
    ) {
        let payload: [String: Any] = [
            "action": "update_memory",
            "memory_id": memoryId,
            "updates": updates
        ]
        
        pythonService.sendCommand(payload) { result in
            switch result {
            case .success(let response):
                guard let memoryData = response as? [String: Any] else {
                    completion(.failure(MemoryError.invalidResponse))
                    return
                }
                completion(.success(memoryData))
            case .failure(let error):
                completion(.failure(error))
            }
        }
    }
    
    /// Delete a memory record.
    ///
    /// - Parameters:
    ///   - memoryId: ID of the memory to delete
    ///   - completion: Completion handler with Result type
    func deleteMemory(
        _ memoryId: String,
        completion: @escaping (Result<Void, Error>) -> Void
    ) {
        let payload: [String: Any] = [
            "action": "delete_memory",
            "memory_id": memoryId
        ]
        
        pythonService.sendCommand(payload) { result in
            switch result {
            case .success:
                completion(.success(()))
            case .failure(let error):
                completion(.failure(error))
            }
        }
    }
}

/// Memory-related errors.
enum MemoryError: Error {
    /// Invalid response format from server.
    case invalidResponse
}
