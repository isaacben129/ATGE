"""Pure scoring: engagement_rate, followers delta from TweetPerformance / API response."""


def engagement_rate(impressions: int, likes: int, retweets: int, replies: int) -> float:
    """Engagement rate = (likes + retweets + replies) / impressions, or 0 if no impressions."""
    if impressions <= 0:
        return 0.0
    return (likes + retweets + replies) / impressions


def followers_gained_delta(performances: list[dict]) -> int:
    """Sum followers_gained across a list of performance dicts (e.g. TweetPerformance rows)."""
    return sum(p.get("followers_gained", 0) or 0 for p in performances)
