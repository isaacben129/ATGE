"""Publishing pipeline: fetch approved unpublished candidates, post via Twitter API, store tweet IDs. Threads posted as reply chains."""
from atg_engine.agents import create_publisher
from atg_engine.config.env_validation import validate_env
from atg_engine.db.session import SessionLocal
from atg_engine.models import TweetCandidate, TweetPerformance
from atg_engine.services import twitter_api


def run(**kwargs) -> str:
    validate_env(require_llm=False, require_twitter=True)
    if kwargs.get("dry_run") or kwargs.get("preview"):
        return _preview_publish(kwargs.get("limit", 5))
    db = SessionLocal()
    try:
        candidates = (
            db.query(TweetCandidate)
            .filter(TweetCandidate.approved == True, TweetCandidate.published == False)
            .order_by(TweetCandidate.created_at, TweetCandidate.thread_id, TweetCandidate.thread_sequence)
            .all()
        )
        if not candidates:
            return "No unpublished approved candidates."
        limit = kwargs.get("limit", 5)
        results = []
        published_count = 0
        seen_thread_ids = set()
        i = 0
        while i < len(candidates) and published_count < limit:
            c = candidates[i]
            if c.thread_id and c.thread_id in seen_thread_ids:
                i += 1
                continue
            if c.thread_id and c.thread_sequence is not None and c.thread_sequence == 0:
                thread_candidates = [x for x in candidates[i:] if x.thread_id == c.thread_id and not x.published]
                thread_candidates.sort(key=lambda x: (x.thread_sequence or 0))
                reply_to_id = None
                for tc in thread_candidates:
                    if published_count >= limit:
                        break
                    tweet_id = twitter_api.post_tweet(tc.text, reply_to_tweet_id=reply_to_id)
                    if tweet_id:
                        tc.published = True
                        tc.tweet_id = tweet_id
                        perf = TweetPerformance(tweet_id=tweet_id, candidate_id=tc.id)
                        db.add(perf)
                        results.append(f"Published candidate {tc.id} (thread) -> tweet_id {tweet_id}")
                        published_count += 1
                        reply_to_id = tweet_id
                    else:
                        results.append(f"Failed to publish candidate {tc.id}")
                        break
                seen_thread_ids.add(c.thread_id)
                i += len(thread_candidates)
                continue
            if c.thread_id and c.thread_sequence is not None and c.thread_sequence > 0:
                i += 1
                continue
            quote_id = getattr(c, "quote_tweet_id", None)
            tweet_id = twitter_api.post_tweet(c.text, quote_tweet_id=quote_id)
            if tweet_id:
                c.published = True
                c.tweet_id = tweet_id
                perf = TweetPerformance(tweet_id=tweet_id, candidate_id=c.id)
                db.add(perf)
                results.append(f"Published candidate {c.id} -> tweet_id {tweet_id}")
                published_count += 1
            else:
                results.append(f"Failed to publish candidate {c.id}")
            i += 1
        db.commit()
        return "\n".join(results)
    finally:
        db.close()


def _preview_publish(limit: int) -> str:
    """List what would be published (and in what order for threads) without posting."""
    db = SessionLocal()
    try:
        candidates = (
            db.query(TweetCandidate)
            .filter(TweetCandidate.approved == True, TweetCandidate.published == False)
            .order_by(TweetCandidate.created_at, TweetCandidate.thread_id, TweetCandidate.thread_sequence)
            .all()
        )
        if not candidates:
            return "[dry-run] No unpublished approved candidates."
        lines = [f"[dry-run] Would publish (limit={limit}):"]
        seen_thread_ids = set()
        count = 0
        i = 0
        while i < len(candidates) and count < limit:
            c = candidates[i]
            if c.thread_id and c.thread_id in seen_thread_ids:
                i += 1
                continue
            if c.thread_id and c.thread_sequence is not None and c.thread_sequence == 0:
                thread_candidates = [x for x in candidates[i:] if x.thread_id == c.thread_id]
                thread_candidates.sort(key=lambda x: (x.thread_sequence or 0))
                lines.append(f"  Thread (candidates {[x.id for x in thread_candidates]}):")
                for tc in thread_candidates:
                    if count >= limit:
                        break
                    preview_text = tc.text[:60] + "..." if len(tc.text) > 60 else tc.text
                    lines.append(f"    {tc.id}: {preview_text}")
                    count += 1
                seen_thread_ids.add(c.thread_id)
                i += len(thread_candidates)
                continue
            if c.thread_id and c.thread_sequence is not None and c.thread_sequence > 0:
                i += 1
                continue
            preview_text = c.text[:60] + "..." if len(c.text) > 60 else c.text
            quote_note = f" (quote of {c.quote_tweet_id})" if getattr(c, "quote_tweet_id", None) else ""
            lines.append(f"  {c.id}: {preview_text}{quote_note}")
            count += 1
            i += 1
        return "\n".join(lines)
    finally:
        db.close()
