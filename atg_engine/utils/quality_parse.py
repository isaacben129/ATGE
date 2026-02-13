"""Parse quality scorer output for quality scores per item."""
import re


def parse_quality_scores(quality_output: str) -> dict[str, float]:
    """
    Parse quality scorer output for TWEET: / QUALITY_SCORE: blocks.
    Returns dict mapping tweet text (normalized) -> quality score (0-10).
    
    Expected format:
    TWEET: <text>
    CLARITY: <0-10>
    HOOK_STRENGTH: <0-10>
    ENGAGEMENT_POTENTIAL: <0-10>
    PERSONA_ALIGNMENT: <0-10>
    QUALITY_SCORE: <0-10>
    
    Or simplified:
    TWEET: <text>
    QUALITY_SCORE: <0-10>
    """
    scores = {}
    lines = quality_output.strip().split("\n")
    current_text = ""
    current_score = None
    
    for i, line in enumerate(lines):
        line_upper = line.upper().strip()
        
        # Check for TWEET: marker
        if line_upper.startswith("TWEET:"):
            # Save previous entry if exists
            if current_text.strip() and current_score is not None:
                scores[current_text.strip()] = current_score
            
            # Extract tweet text
            text = line[6:].strip()  # Remove "TWEET:" prefix
            current_text = text
            current_score = None
        
        # Check for QUALITY_SCORE: marker
        elif "QUALITY_SCORE:" in line_upper:
            # Extract score
            match = re.search(r"QUALITY_SCORE:\s*([\d.]+)", line_upper)
            if match:
                try:
                    score = float(match.group(1))
                    # Clamp to 0-10 range
                    score = max(0.0, min(10.0, score))
                    current_score = score
                except ValueError:
                    pass
        
        # Also check for individual dimension scores and use overall if available
        elif any(dim in line_upper for dim in ["CLARITY:", "HOOK_STRENGTH:", "ENGAGEMENT_POTENTIAL:", "PERSONA_ALIGNMENT:"]):
            # If we have a current text but no score yet, try to extract from this line
            if current_text and current_score is None:
                # Look for a number in the line
                match = re.search(r"([\d.]+)", line)
                if match:
                    try:
                        score = float(match.group(1))
                        score = max(0.0, min(10.0, score))
                        current_score = score
                    except ValueError:
                        pass
    
    # Save last entry
    if current_text.strip() and current_score is not None:
        scores[current_text.strip()] = current_score
    
    # Fallback: try to extract scores from any line with "QUALITY_SCORE:" or "SCORE:"
    if not scores:
        for line in lines:
            if "QUALITY_SCORE:" in line.upper() or "SCORE:" in line.upper():
                # Try to find tweet text nearby (within 5 lines)
                line_idx = lines.index(line)
                for offset in range(-5, 6):
                    check_idx = line_idx + offset
                    if 0 <= check_idx < len(lines):
                        check_line = lines[check_idx]
                        if "TWEET:" in check_line.upper():
                            text = check_line[6:].strip()
                            match = re.search(r"([\d.]+)", line)
                            if match:
                                try:
                                    score = float(match.group(1))
                                    score = max(0.0, min(10.0, score))
                                    scores[text] = score
                                except ValueError:
                                    pass
                            break
    
    return scores
