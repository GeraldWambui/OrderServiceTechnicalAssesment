import time
from typing import Any, Optional


class Node:
    def __init__(self, key: Any, value: Any, expire_time: float):
        self.key = key
        self.value = value
        self.expire_time = expire_time
        self.prev: Optional['Node'] = None
        self.next: Optional['Node'] = None


class LRUCacheWithTTL:
    """
    LRU Cache with TTL support
    - get(key): O(1) average case
    - put(key, value, ttl_ms): O(1) average case
    - Automatic expiration of entries based on TTL
    """
    
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        
        self.capacity = capacity
        self.cache = {}  
        
        self.head = Node(None, None, 0)
        self.tail = Node(None, None, 0)
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def _remove_node(self, node: Node) -> None:
        """Remove node from doubly linked list"""
        node.prev.next = node.next
        node.next.prev = node.prev
    
    def _add_to_head(self, node: Node) -> None:
        """Add node right after head (most recently used position)"""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node
    
    def _move_to_head(self, node: Node) -> None:
        """Move existing node to head (mark as recently used)"""
        self._remove_node(node)
        self._add_to_head(node)
    
    def _remove_tail(self) -> Node:
        """Remove least recently used node (before tail)"""
        lru_node = self.tail.prev
        self._remove_node(lru_node)
        return lru_node
    
    def _is_expired(self, node: Node) -> bool:
        """Check if node has expired based on TTL"""
        return time.time() * 1000 >= node.expire_time
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries (lazy cleanup)"""
        expired_keys = []
        for key, node in self.cache.items():
            if self._is_expired(node):
                expired_keys.append(key)
        
        for key in expired_keys:
            node = self.cache[key]
            self._remove_node(node)
            del self.cache[key]
    
    def get(self, key: Any) -> Any:
        """
        Get value by key. Returns None if key doesn't exist or has expired.
        O(1) average time complexity.
        """
        if key not in self.cache:
            return None
        
        node = self.cache[key]
        
        if self._is_expired(node):
            self._remove_node(node)
            del self.cache[key]
            return None
        
        self._move_to_head(node)
        return node.value
    
    def put(self, key: Any, value: Any, ttl_ms: int) -> None:
        """
        Put key-value pair with TTL in milliseconds.
        O(1) average time complexity.
        """
        if ttl_ms <= 0:
            raise ValueError("TTL must be positive")
        
        current_time_ms = time.time() * 1000
        expire_time = current_time_ms + ttl_ms
        
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            node.expire_time = expire_time
            self._move_to_head(node)
        else:
            new_node = Node(key, value, expire_time)
            
            if len(self.cache) >= self.capacity:
                self._cleanup_expired()
                
                if len(self.cache) >= self.capacity:
                    lru_node = self._remove_tail()
                    del self.cache[lru_node.key]
            
            self.cache[key] = new_node
            self._add_to_head(new_node)
    
    def size(self) -> int:
        """Return current cache size (including expired but not cleaned up entries)"""
        return len(self.cache)
    
    def clear(self) -> None:
        """Clear all entries"""
        self.cache.clear()
        self.head.next = self.tail
        self.tail.prev = self.head


# Comprehensive test suite
def test_lru_cache_with_ttl():
    print("Running LRU Cache with TTL tests...")
    
    # Test 1: Basic functionality
    print("\n1. Testing basic get/put operations...")
    cache = LRUCacheWithTTL(3)
    
    cache.put("a", 1, 5000)  
    cache.put("b", 2, 5000)
    cache.put("c", 3, 5000)
    
    assert cache.get("a") == 1
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert cache.get("d") is None  
    print("✓ Basic operations work correctly")
    
    # Test 2: LRU eviction
    print("\n2. Testing LRU eviction...")
    cache.clear()
    cache.put("a", 1, 5000)
    cache.put("b", 2, 5000)
    cache.put("c", 3, 5000)
    
    # Access 'a' to make it recently used
    cache.get("a")
    
    # Add new item, should evict 'b' (least recently used)
    cache.put("d", 4, 5000)
    
    assert cache.get("a") == 1  # Still exists
    assert cache.get("b") is None  # Evicted
    assert cache.get("c") == 3  # Still exists
    assert cache.get("d") == 4  # Newly added
    print("✓ LRU eviction works correctly")
    
    # Test 3: TTL expiration
    print("\n3. Testing TTL expiration...")
    cache.clear()
    cache.put("short", "expires_soon", 100)  # 100ms TTL
    cache.put("long", "stays_longer", 5000)  # 5s TTL
    
    assert cache.get("short") == "expires_soon"
    assert cache.get("long") == "stays_longer"
    
    # Wait for short TTL to expire
    time.sleep(0.2)  # 200ms
    
    assert cache.get("short") is None  # Should be expired
    assert cache.get("long") == "stays_longer"  # Should still exist
    print("✓ TTL expiration works correctly")
    
    # Test 4: Update existing key
    print("\n4. Testing key updates...")
    cache.clear()
    cache.put("key", "value1", 5000)
    assert cache.get("key") == "value1"
    
    cache.put("key", "value2", 5000)  # Update same key
    assert cache.get("key") == "value2"
    assert cache.size() == 1  # Size shouldn't increase
    print("✓ Key updates work correctly")
    
    # Test 5: Capacity limits
    print("\n5. Testing capacity limits...")
    small_cache = LRUCacheWithTTL(2)
    small_cache.put("a", 1, 5000)
    small_cache.put("b", 2, 5000)
    assert small_cache.size() == 2
    
    small_cache.put("c", 3, 5000)  # Should evict 'a'
    assert small_cache.size() == 2
    assert small_cache.get("a") is None  # Evicted
    assert small_cache.get("b") == 2
    assert small_cache.get("c") == 3
    print("✓ Capacity limits enforced correctly")
    
    # Test 6: Mixed TTL and LRU behavior
    print("\n6. Testing mixed TTL and LRU behavior...")
    cache = LRUCacheWithTTL(3)
    cache.put("a", 1, 200)   # Short TTL
    cache.put("b", 2, 5000)  # Long TTL
    cache.put("c", 3, 5000)  # Long TTL
    
    # Wait for 'a' to expire
    time.sleep(0.3)
    
    # Add new item - should use space from expired 'a', not evict LRU
    cache.put("d", 4, 5000)
    
    assert cache.get("a") is None  # Expired
    assert cache.get("b") == 2     # Still exists
    assert cache.get("c") == 3     # Still exists  
    assert cache.get("d") == 4     # Newly added
    print("✓ Mixed TTL and LRU behavior works correctly")
    
    # Test 7: Edge cases
    print("\n7. Testing edge cases...")
    
    # Test invalid capacity
    try:
        LRUCacheWithTTL(0)
        assert False, "Should raise ValueError"
    except ValueError:
        pass
    
    # Test invalid TTL
    cache = LRUCacheWithTTL(1)
    try:
        cache.put("key", "value", 0)
        assert False, "Should raise ValueError"
    except ValueError:
        pass
    
    # Test very short TTL
    cache.put("fast", "gone", 1)  # 1ms TTL
    time.sleep(0.01)  # 10ms
    assert cache.get("fast") is None
    
    print("✓ Edge cases handled correctly")
    
    print("\n🎉 All tests passed! LRU Cache with TTL implementation is working correctly.")


# Performance test
def performance_test():
    print("\n" + "="*50)
    print("Performance Test")
    print("="*50)
    
    cache = LRUCacheWithTTL(1000)
    
    # Test put performance
    start_time = time.time()
    for i in range(10000):
        cache.put(f"key_{i}", f"value_{i}", 10000)
    put_time = time.time() - start_time
    
    # Test get performance
    start_time = time.time()
    for i in range(10000):
        cache.get(f"key_{i}")
    get_time = time.time() - start_time
    
    print(f"Put 10,000 items: {put_time:.4f} seconds ({10000/put_time:.0f} ops/sec)")
    print(f"Get 10,000 items: {get_time:.4f} seconds ({10000/get_time:.0f} ops/sec)")


if __name__ == "__main__":
    test_lru_cache_with_ttl()
    performance_test()