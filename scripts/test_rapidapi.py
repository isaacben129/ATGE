"""Test RapidAPI Twitter integration.
Run from project root: python scripts/test_rapidapi.py
"""
import sys
import time
from pathlib import Path

# Ensure atg_engine is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atg_engine.config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST, RAPIDAPI_TWITTER_USERNAME
from atg_engine.services import rapidapi_client
from atg_engine.services.twitter_search_provider import RapidAPISearchProvider, get_search_provider
from atg_engine.services.twitter_read_provider import RapidAPIReadProvider, get_read_provider


def _safe(s: str, max_len: int = 80) -> str:
    """Avoid UnicodeEncodeError on Windows console."""
    if not s:
        return ""
    return (s[:max_len] + ("..." if len(s) > max_len else "")).encode("ascii", "replace").decode("ascii")


def test_rapidapi_client_direct():
    """Test RapidAPI client functions directly."""
    print("=== Testing RapidAPI Client Directly ===")
    
    if not RAPIDAPI_KEY:
        print("[X] RAPIDAPI_KEY not set in .env")
        print("   Add RAPIDAPI_KEY=your-key to .env file")
        return False
    
    print(f"[OK] RAPIDAPI_KEY configured (length: {len(RAPIDAPI_KEY)})")
    print(f"[OK] RAPIDAPI_HOST: {RAPIDAPI_HOST}")
    
    # Test search
    print("\n--- Testing search_tweets_by_keywords ---")
    try:
        tweets, next_cursor = rapidapi_client.search_tweets_by_keywords(
            keywords="dating",
            limit=5,
            search_type="Top"
        )
        print(f"[OK] Search successful: {len(tweets)} tweets returned")
        if tweets:
            t = tweets[0]
            print(f"  First tweet:")
            print(f"    ID: {t.get('tweet_id')}")
            print(f"    Author: @{t.get('author_username')}")
            print(f"    Likes: {t.get('likes')}, Retweets: {t.get('retweets')}, Replies: {t.get('replies')}")
            print(f"    Text: {_safe(t.get('text') or '', 100)}")
            if next_cursor:
                print(f"    Next cursor available: {next_cursor[:50]}...")
        else:
            print("  [WARN] No tweets returned")
    except Exception as e:
        print(f"[ERROR] Search failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test follower count
    print("\n--- Testing get_user_follower_count ---")
    try:
        count = rapidapi_client.get_user_follower_count("elonmusk")
        if count is not None:
            print(f"[OK] Follower count successful: {count:,} followers")
        else:
            print("  [WARN] Follower count returned None")
    except Exception as e:
        print(f"[ERROR] Follower count failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test metrics batch
    print("\n--- Testing get_tweet_metrics_batch ---")
    try:
        if tweets:
            tweet_ids = [tweets[0].get('tweet_id')]
            metrics = rapidapi_client.get_tweet_metrics_batch(tweet_ids)
            print(f"[OK] Metrics batch successful: {len(metrics)} results")
            if metrics:
                tid = list(metrics.keys())[0]
                m = metrics[tid]
                print(f"  Tweet {tid}: impressions={m.get('impressions')}, likes={m.get('likes')}, "
                      f"retweets={m.get('retweets')}, replies={m.get('replies')}")
        else:
            print("  [WARN] Skipping metrics test (no tweets available)")
    except Exception as e:
        print(f"[ERROR] Metrics batch failed: {e}")
        return False
    
    return True


def test_search_provider():
    """Test RapidAPI search provider."""
    print("\n=== Testing RapidAPI Search Provider ===")
    
    if not RAPIDAPI_KEY:
        print("[X] RAPIDAPI_KEY not set, skipping provider test")
        return False
    
    try:
        provider = RapidAPISearchProvider()
        
        print("--- Testing search_recent_tweets (low thresholds) ---")
        results = provider.search_recent_tweets(
            query="dating",
            max_results=5,
            min_likes=0,
            min_retweets=0,
        )
        print(f"[OK] Search provider returned {len(results)} tweets")
        if results:
            t = results[0]
            print(f"  First result:")
            print(f"    ID: {t.get('tweet_id')}")
            print(f"    Author: @{t.get('author_username')}")
            print(f"    Likes: {t.get('likes')}, Retweets: {t.get('retweets')}")
            print(f"    Text: {_safe(t.get('text') or '', 80)}")
        
        print("\n--- Testing search_recent_tweets (with filters) ---")
        filtered = provider.search_recent_tweets(
            query="dating",
            max_results=5,
            min_likes=10,
            min_retweets=5,
        )
        print(f"[OK] Filtered search returned {len(filtered)} tweets (min_likes=10, min_retweets=5)")
        
        return True
    except Exception as e:
        print(f"[ERROR] Search provider test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_read_provider():
    """Test RapidAPI read provider."""
    print("\n=== Testing RapidAPI Read Provider ===")
    
    if not RAPIDAPI_KEY:
        print("[X] RAPIDAPI_KEY not set, skipping provider test")
        return False
    
    try:
        provider = RapidAPIReadProvider()
        
        print("--- Testing get_tweet_metrics_batch ---")
        test_ids = ["1703108627035254988"]
        metrics = provider.get_tweet_metrics_batch(test_ids)
        print(f"[OK] Metrics batch returned {len(metrics)} results")
        if metrics:
            tid = list(metrics.keys())[0]
            m = metrics[tid]
            print(f"  Tweet {tid}: {m}")
        
        print("\n--- Testing get_me_follower_count ---")
        if RAPIDAPI_TWITTER_USERNAME:
            count = provider.get_me_follower_count()
            if count is not None:
                print(f"[OK] Follower count: {count:,}")
            else:
                print("  [WARN] Follower count returned None")
        else:
            print("  [WARN] RAPIDAPI_TWITTER_USERNAME not set, skipping follower count test")
        
        return True
    except Exception as e:
        print(f"[ERROR] Read provider test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Test full integration through provider chain."""
    print("\n=== Testing Full Integration (via get_search_provider) ===")
    
    if not RAPIDAPI_KEY:
        print("[X] RAPIDAPI_KEY not set, skipping integration test")
        return False
    
    try:
        provider = get_search_provider()
        print(f"[OK] Got search provider: {type(provider).__name__}")
        
        results = provider.search_recent_tweets(
            query="dating",
            max_results=3,
            min_likes=0,
            min_retweets=0,
        )
        print(f"[OK] Integration search returned {len(results)} tweets")
        
        return True
    except Exception as e:
        print(f"[ERROR] Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_caching():
    """Test that caching works."""
    print("\n=== Testing Caching ===")
    
    if not RAPIDAPI_KEY:
        print("[X] RAPIDAPI_KEY not set, skipping cache test")
        return False
    
    try:
        # First request
        start1 = time.time()
        tweets1, _ = rapidapi_client.search_tweets_by_keywords("dating", limit=3, search_type="Top")
        time1 = time.time() - start1
        print(f"[OK] First request: {len(tweets1)} tweets in {time1:.3f}s")
        
        # Second request (should be cached)
        start2 = time.time()
        tweets2, _ = rapidapi_client.search_tweets_by_keywords("dating", limit=3, search_type="Top")
        time2 = time.time() - start2
        print(f"[OK] Second request: {len(tweets2)} tweets in {time2:.3f}s")
        
        if time2 < time1 * 0.5:
            print("  [OK] Caching appears to be working (second request much faster)")
        else:
            print("  [WARN] Caching may not be working (second request not significantly faster)")
        
        return True
    except Exception as e:
        print(f"[ERROR] Cache test failed: {e}")
        return False


def main():
    print("RapidAPI Twitter Integration Test")
    print("=" * 50)
    
    results = []
    
    results.append(("Client Direct", test_rapidapi_client_direct()))
    results.append(("Search Provider", test_search_provider()))
    results.append(("Read Provider", test_read_provider()))
    results.append(("Integration", test_integration()))
    results.append(("Caching", test_caching()))
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}: {name}")
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed!")
    else:
        print(f"\n[WARN] {total - passed} test(s) failed")


if __name__ == "__main__":
    main()
