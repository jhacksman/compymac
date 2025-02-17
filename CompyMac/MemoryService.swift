//
//  MemoryService.swift
//  compymac
//
//  Memory service for handling WebSocket-based memory operations.
//

import Foundation

/// Memory service singleton for handling memory operations.
public class MemoryService {
    /// Shared instance for singleton access.
    public static let shared = MemoryService()
    
    /// Python service for WebSocket communication.
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
    public func storeMemory(
        _ content: String,
        metadata: [String: Any]
    ) async throws -> Result<[String: Any], Error> {
        let payload: [String: Any] = [
            "action": "store_memory",
            "content": content,
            "metadata": metadata,
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]
        
        let result = try await pythonService.sendCommand("store_memory", payload: payload)
        switch result {
        case .success(let response):
            guard let memoryData = response as? [String: Any] else {
                return .failure(MemoryError.invalidResponse)
            }
            return .success(memoryData)
        case .failure(let error):
            return .failure(error)
        }
    }
    
    /// Retrieve context using hybrid query approach.
    ///
    /// - Parameters:
    ///   - query: Search query for semantic similarity
    ///   - taskId: Optional task-specific context ID
    ///   - timeRange: Optional time range filter (e.g., "1d", "7d")
    ///   - completion: Completion handler with Result type
    public func retrieveContext(
        query: String,
        taskId: String? = nil,
        timeRange: String? = nil
    ) async throws -> Result<[[String: Any]], Error> {
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
        
        let result = try await pythonService.sendCommand("retrieve_context", payload: payload)
        switch result {
        case .success(let response):
            guard let contextData = response as? [[String: Any]] else {
                return .failure(MemoryError.invalidResponse)
            }
            return .success(contextData)
        case .failure(let error):
            return .failure(error)
        }
    }
    
    /// Update an existing memory record.
    ///
    /// - Parameters:
    ///   - memoryId: ID of the memory to update
    ///   - updates: Dictionary of fields to update
    ///   - completion: Completion handler with Result type
    public func updateMemory(
        _ memoryId: String,
        updates: [String: Any]
    ) async throws -> Result<[String: Any], Error> {
        let payload: [String: Any] = [
            "action": "update_memory",
            "memory_id": memoryId,
            "updates": updates
        ]
        
        let result = try await pythonService.sendCommand("update_memory", payload: payload)
        switch result {
        case .success(let response):
            guard let memoryData = response as? [String: Any] else {
                return .failure(MemoryError.invalidResponse)
            }
            return .success(memoryData)
        case .failure(let error):
            return .failure(error)
        }
    }
    
    /// Delete a memory record.
    ///
    /// - Parameters:
    ///   - memoryId: ID of the memory to delete
    ///   - completion: Completion handler with Result type
    public func deleteMemory(
        _ memoryId: String
    ) async throws -> Result<Void, Error> {
        let payload: [String: Any] = [
            "action": "delete_memory",
            "memory_id": memoryId
        ]
        
        let result = try await pythonService.sendCommand("delete_memory", payload: payload)
        switch result {
        case .success:
            return .success(())
        case .failure(let error):
            return .failure(error)
        }
    }
}

/// Memory-related errors.
public enum MemoryError: Error {
    /// Invalid response format from server.
    case invalidResponse
}
