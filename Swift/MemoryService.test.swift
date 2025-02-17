//
//  MemoryService.test.swift
//  compymac
//
//  Tests for memory service.
//

import XCTest
@testable import compymac

class MemoryServiceTests: XCTestCase {
    var mockPythonService: MockPythonBrowserService!
    var memoryService: MemoryService!
    
    override func setUp() {
        super.setUp()
        mockPythonService = MockPythonBrowserService()
        memoryService = MemoryService.shared
        // Inject mock service
        memoryService.pythonService = mockPythonService
    }
    
    func testStoreMemorySuccess() {
        let expectation = XCTestExpectation(description: "Store memory")
        
        let mockMemory: [String: Any] = [
            "id": "test_id",
            "content": "test memory",
            "metadata": ["importance": "high"],
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]
        mockPythonService.mockResponse = mockMemory
        
        memoryService.storeMemory(
            "test memory",
            metadata: ["importance": "high"]
        ) { result in
            switch result {
            case .success(let memory):
                XCTAssertEqual(memory["id"] as? String, "test_id")
                XCTAssertEqual(memory["content"] as? String, "test memory")
            case .failure(let error):
                XCTFail("Unexpected error: \(error)")
            }
            expectation.fulfill()
        }
        
        wait(for: [expectation], timeout: 1.0)
    }
    
    func testRetrieveContextSuccess() {
        let expectation = XCTestExpectation(description: "Retrieve context")
        
        let mockContext: [[String: Any]] = [[
            "id": "test_id",
            "content": "test memory",
            "metadata": ["importance": "high"],
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]]
        mockPythonService.mockResponse = mockContext
        
        memoryService.retrieveContext(
            query: "test query",
            taskId: "task_123",
            timeRange: "1d"
        ) { result in
            switch result {
            case .success(let context):
                XCTAssertEqual(context.count, 1)
                XCTAssertEqual(context[0]["id"] as? String, "test_id")
            case .failure(let error):
                XCTFail("Unexpected error: \(error)")
            }
            expectation.fulfill()
        }
        
        wait(for: [expectation], timeout: 1.0)
    }
    
    func testUpdateMemorySuccess() {
        let expectation = XCTestExpectation(description: "Update memory")
        
        let mockMemory: [String: Any] = [
            "id": "test_id",
            "content": "updated memory",
            "metadata": ["importance": "high"],
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]
        mockPythonService.mockResponse = mockMemory
        
        memoryService.updateMemory(
            "test_id",
            updates: ["content": "updated memory"]
        ) { result in
            switch result {
            case .success(let memory):
                XCTAssertEqual(memory["content"] as? String, "updated memory")
            case .failure(let error):
                XCTFail("Unexpected error: \(error)")
            }
            expectation.fulfill()
        }
        
        wait(for: [expectation], timeout: 1.0)
    }
    
    func testDeleteMemorySuccess() {
        let expectation = XCTestExpectation(description: "Delete memory")
        
        mockPythonService.mockResponse = nil
        
        memoryService.deleteMemory("test_id") { result in
            switch result {
            case .success:
                break // Expected success
            case .failure(let error):
                XCTFail("Unexpected error: \(error)")
            }
            expectation.fulfill()
        }
        
        wait(for: [expectation], timeout: 1.0)
    }
}

/// Mock Python service for testing.
class MockPythonBrowserService: PythonBrowserService {
    var mockResponse: Any?
    
    override func sendCommand(
        _ payload: [String: Any],
        completion: @escaping (Result<Any, Error>) -> Void
    ) {
        if let response = mockResponse {
            completion(.success(response))
        } else {
            completion(.success(()))
        }
    }
}
