"""Publishing pipeline: fetch approved unpublished candidates, post via Twitter API, store tweet IDs. Threads posted as reply chains."""
import logging

from atg_engine.config.env_validation import validate_env
from atg_engine.db.init_db import _add_missing_tweet_candidate_columns
from atg_engine.db.session import SessionLocal
from atg_engine.models import TweetCandidate, TweetPerformance
from atg_engine.services import twitter_api
from atg_engine.services.twitter_api import DuplicateContentError, TwitterPermanentError

logger = logging.getLogger(__name__)


def _mark_candidate_skipped(c: TweetCandidate, reason: str) -> str:
    """Mark candidate as published with no tweet_id so it is never retried. Returns message for results."""
    c.published = True
    c.tweet_id = None
    return f"Skipped candidate {c.id} ({reason})"


def run(**kwargs) -> str:
    validate_env(require_llm=False, require_twitter=True)
    if kwargs.get("dry_run") or kwargs.get("preview"):
        return _preview_publish(kwargs.get("limit", 5))
    try:
        _add_missing_tweet_candidate_columns()
    except Exception as e:
        logger.warning("Schema self-heal skipped: %s", e)
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
        # Content deduplication: avoid posting text we already posted (reduces 403 duplicate)
        rows = db.query(TweetCandidate.text).filter(
            TweetCandidate.published == True,
            TweetCandidate.tweet_id.is_not(None),
            TweetCandidate.text.is_not(None),
        ).all()
        published_texts: set[str] = {r[0] for r in rows if r[0]}
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
                try:
                    for tc in thread_candidates:
                        if published_count >= limit:
                            break
                        if tc.text in published_texts:
                            results.append(_mark_candidate_skipped(tc, "duplicate content"))
                            db.commit()
                            break
                        try:
                            tweet_id = twitter_api.post_tweet(tc.text, reply_to_tweet_id=reply_to_id)
                        except DuplicateContentError:
                            results.append(_mark_candidate_skipped(tc, "duplicate content"))
                            db.commit()
                            break
                        except TwitterPermanentError:
                            results.append(_mark_candidate_skipped(tc, "permanent failure"))
                            db.commit()
                            break
                        if tweet_id:
                            tc.published = True
                            tc.tweet_id = tweet_id
                            published_texts.add(tc.text)
                            perf = TweetPerformance(tweet_id=tweet_id, candidate_id=tc.id)
                            db.add(perf)
                            results.append(f"Published candidate {tc.id} (thread) -> tweet_id {tweet_id}")
                            published_count += 1
                            reply_to_id = tweet_id
                            db.commit()
                        else:
                            results.append(f"Failed to publish candidate {tc.id}")
                            break
                except (DuplicateContentError, TwitterPermanentError):
                    raise
                except Exception as e:
                    logger.exception("Failed to publish thread: %s", e)
                    results.append(f"Failed thread (candidate {c.id}): {e}")
                seen_thread_ids.add(c.thread_id)
                i += len(thread_candidates)
                continue
            if c.thread_id and c.thread_sequence is not None and c.thread_sequence > 0:
                i += 1
                continue
            if c.text in published_texts:
                results.append(_mark_candidate_skipped(c, "duplicate content"))
                db.commit()
                i += 1
                continue
            try:
                quote_id = getattr(c, "quote_tweet_id", None)
                tweet_id = twitter_api.post_tweet(c.text, quote_tweet_id=quote_id)
                if tweet_id:
                    c.published = True
                    c.tweet_id = tweet_id
                    published_texts.add(c.text)
                    perf = TweetPerformance(tweet_id=tweet_id, candidate_id=c.id)
                    db.add(perf)
                    results.append(f"Published candidate {c.id} -> tweet_id {tweet_id}")
                    published_count += 1
                    db.commit()
                else:
                    results.append(f"Failed to publish candidate {c.id}")
            except DuplicateContentError:
                results.append(_mark_candidate_skipped(c, "duplicate content"))
                db.commit()
            except TwitterPermanentError:
                results.append(_mark_candidate_skipped(c, "permanent failure"))
                db.commit()
            except Exception as e:
                logger.exception("Failed to publish candidate %s: %s", c.id, e)
                results.append(f"Failed candidate {c.id}: {e}")
            i += 1
        return "\n".join(results)
    finally:
        db.close()


def _preview_publish(limit: int) -> str:
    """List what would be published (and in what order for threads) without posting."""
    try:
        _add_missing_tweet_candidate_columns()
    except Exception as e:
        logger.warning("Schema self-heal skipped: %s", e)
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
